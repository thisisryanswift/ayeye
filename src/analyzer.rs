use anyhow::{anyhow, Context, Result};
use serde::{Deserialize, Serialize};
use std::path::Path;

use crate::config;

#[derive(Debug, Serialize, Deserialize)]
pub struct Analysis {
    pub title: String,
    pub summary: String,
    pub steps: Vec<String>,
    pub timestamps: Vec<Timestamp>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct Timestamp {
    pub time: String,
    #[serde(default)]
    pub description: String,
}

pub async fn analyze(video_path: &Path) -> Result<Analysis> {
    let api_key = config::gemini_api_key()
        .ok_or_else(|| anyhow!("GEMINI_API_KEY not set"))?;
    
    let client = reqwest::Client::new();
    
    // If MKV, convert to MP4 first (Gemini doesn't like MKV)
    let (final_path, _temp_file) = if video_path.extension().map(|e| e == "mkv").unwrap_or(false) {
        eprintln!("Converting MKV to MP4 for upload...");
        let mp4_path = video_path.with_extension("mp4");
        
        let output = tokio::process::Command::new("ffmpeg")
            .args([
                "-y", "-i", video_path.to_str().unwrap(),
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                mp4_path.to_str().unwrap()
            ])
            .output()
            .await
            .context("Failed to run ffmpeg - is it installed?")?;
        
        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Err(anyhow!("ffmpeg conversion failed: {}", stderr));
        }
        
        // Return path and keep temp file reference
        (mp4_path.clone(), Some(mp4_path))
    } else {
        (video_path.to_path_buf(), None)
    };
    
    // Read the file
    let file_bytes = tokio::fs::read(&final_path).await?;
    let file_size = file_bytes.len();
    let file_name = final_path.file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("video.mp4");
    
    let mime_type = "video/mp4";
    
    eprintln!("Uploading {} ({} bytes, {})...", file_name, file_size, mime_type);
    
    // Step 1: Start resumable upload
    let start_url = format!(
        "https://generativelanguage.googleapis.com/upload/v1beta/files?key={}",
        api_key
    );
    
    let metadata = serde_json::json!({
        "file": {
            "display_name": file_name
        }
    });
    
    let start_response = client.post(&start_url)
        .header("X-Goog-Upload-Protocol", "resumable")
        .header("X-Goog-Upload-Command", "start")
        .header("X-Goog-Upload-Header-Content-Length", file_size.to_string())
        .header("X-Goog-Upload-Header-Content-Type", mime_type)
        .header("Content-Type", "application/json")
        .json(&metadata)
        .send()
        .await?;
    
    if !start_response.status().is_success() {
        let error_text = start_response.text().await?;
        return Err(anyhow!("Upload start failed: {}", error_text));
    }
    
    // Get the upload URL from response header
    let upload_url = start_response
        .headers()
        .get("x-goog-upload-url")
        .and_then(|v| v.to_str().ok())
        .ok_or_else(|| anyhow!("No upload URL in response"))?
        .to_string();
    
    // Step 2: Upload the file data
    let upload_response = client.post(&upload_url)
        .header("X-Goog-Upload-Command", "upload, finalize")
        .header("X-Goog-Upload-Offset", "0")
        .header("Content-Length", file_size.to_string())
        .body(file_bytes)
        .send()
        .await?;
    
    if !upload_response.status().is_success() {
        let error_text = upload_response.text().await?;
        return Err(anyhow!("Upload failed: {}", error_text));
    }
    
    #[derive(Deserialize)]
    struct UploadResponse {
        file: FileInfo,
    }
    
    #[derive(Deserialize)]
    struct FileInfo {
        name: String,
        uri: String,
    }
    
    let upload_result: UploadResponse = upload_response.json().await?;
    let file_uri = upload_result.file.uri;
    
    eprintln!("Upload complete, waiting for processing...");
    
    // Wait for processing
    loop {
        let status_url = format!(
            "https://generativelanguage.googleapis.com/v1beta/{}?key={}",
            upload_result.file.name,
            api_key
        );
        
        let status_response = client.get(&status_url).send().await?;
        
        #[derive(Deserialize)]
        struct StatusResponse {
            state: String,
        }
        
        let status_text = status_response.text().await?;
        let status: StatusResponse = serde_json::from_str(&status_text)
            .map_err(|e| anyhow!("Failed to parse status: {}. Response: {}", e, status_text))?;
        
        eprintln!("File status: {}", status.state);
        
        if status.state == "ACTIVE" {
            break;
        } else if status.state == "FAILED" {
            return Err(anyhow!("Video processing failed. Status response: {}", status_text));
        }
        
        tokio::time::sleep(tokio::time::Duration::from_secs(2)).await;
    }
    
    eprintln!("Generating analysis...");
    
    // Generate content
    let generate_url = format!(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={}",
        api_key
    );
    
    let prompt = r#"
    Analyze this screen recording of a software issue. The user is demonstrating a bug or problem.
    
    Extract:
    1. A concise title (max 80 chars)
    2. A summary of the issue (2-3 sentences)
    3. Step-by-step reproduction instructions based on the user's actions
    4. Key timestamps where important actions occur
    
    Respond in JSON format with fields: title, summary, steps (array), timestamps (array of {time, description}).
    "#;
    
    let request_body = serde_json::json!({
        "contents": [{
            "parts": [
                {"file_data": {"mime_type": mime_type, "file_uri": file_uri}},
                {"text": prompt}
            ]
        }],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "title": {"type": "STRING"},
                    "summary": {"type": "STRING"},
                    "steps": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "timestamps": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "time": {"type": "STRING"},
                                "description": {"type": "STRING"}
                            }
                        }
                    }
                },
                "required": ["title", "summary", "steps", "timestamps"]
            }
        }
    });
    
    let response = client.post(&generate_url)
        .json(&request_body)
        .send()
        .await?;
    
    if !response.status().is_success() {
        let error_text = response.text().await?;
        return Err(anyhow!("Generation failed: {}", error_text));
    }
    
    #[derive(Deserialize)]
    struct GenerateResponse {
        candidates: Vec<Candidate>,
    }
    
    #[derive(Deserialize)]
    struct Candidate {
        content: Content,
    }
    
    #[derive(Deserialize)]
    struct Content {
        parts: Vec<Part>,
    }
    
    #[derive(Deserialize)]
    struct Part {
        text: String,
    }
    
    let result: GenerateResponse = response.json().await?;
    
    let text = result.candidates
        .first()
        .and_then(|c| c.content.parts.first())
        .map(|p| &p.text)
        .ok_or_else(|| anyhow!("No response content"))?;
    
    let analysis: Analysis = serde_json::from_str(text)
        .map_err(|e| anyhow!("Failed to parse response: {}. Raw response: {}", e, text))?;
    
    Ok(analysis)
}
