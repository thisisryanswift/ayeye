use anyhow::{Context, Result};
use std::sync::Arc;
use tokio::sync::Notify;
use tokio::io::AsyncBufReadExt;

mod portal;
mod recorder;
mod analyzer;
mod config;

#[tokio::main]
async fn main() -> Result<()> {
    // Load config (for Gemini API key)
    config::load()?;
    
    run_interactive().await
}

async fn run_interactive() -> Result<()> {
    println!("Select a screen or window to record...");
    
    // Get recording path - store in ~/Videos/AyEye
    let recordings_dir = config::recordings_dir()?;
    std::fs::create_dir_all(&recordings_dir)?;
    
    let timestamp = chrono::Local::now().format("%Y%m%d_%H%M%S");
    let output_path = recordings_dir.join(format!("issue_{}.mkv", timestamp));
    
    // Set up portal and get PipeWire node
    let node_id = portal::request_screencast().await
        .context("Failed to set up screen capture")?;
    
    println!("\nRecording! Press Enter to stop...\n");
    
    // Start recording
    let stop_signal = Arc::new(Notify::new());
    let stop_signal_clone = stop_signal.clone();
    
    let output_path_clone = output_path.clone();
    let recording_handle = tokio::spawn(async move {
        recorder::record(node_id, &output_path_clone, stop_signal_clone).await
    });
    
    // Wait for Enter or Ctrl+C
    let mut line = String::new();
    let stdin = tokio::io::stdin();
    let mut reader = tokio::io::BufReader::new(stdin);
    
    tokio::select! {
        _ = reader.read_line(&mut line) => {}
        _ = tokio::signal::ctrl_c() => {}
    }
    
    println!("Stopping recording...");
    stop_signal.notify_one();
    
    recording_handle.await??;
    
    println!("Saved to {}", output_path.display());
    
    // Analyze with Gemini
    println!("Analyzing video...");
    let analysis = analyzer::analyze(&output_path).await
        .context("Failed to analyze video")?;
    
    println!("Analysis complete: {}", analysis.title);
    
    // Save the issue
    let cwd = std::env::current_dir()?;
    
    if is_beads_directory(&cwd) {
        // Create beads issue
        create_beads_issue(&analysis, &output_path).await?;
    } else {
        // Create markdown file in current directory
        create_markdown_issue(&analysis, &output_path, &timestamp.to_string()).await?;
    }
    
    println!("\nDone!");
    
    Ok(())
}

fn is_beads_directory(path: &std::path::Path) -> bool {
    // Check for .beads directory or beads.toml
    path.join(".beads").is_dir() || path.join("beads.toml").is_file()
}

async fn create_beads_issue(analysis: &analyzer::Analysis, video_path: &std::path::Path) -> Result<()> {
    // Use bd CLI to create an issue
    let body = format_issue_body(analysis, video_path);
    
    let output = tokio::process::Command::new("bd")
        .args([
            "create",
            &analysis.title,
            "--type", "bug",
            "--description", &body,
        ])
        .output()
        .await
        .context("Failed to run bd CLI - is it installed?")?;
    
    if output.status.success() {
        let stdout = String::from_utf8_lossy(&output.stdout);
        println!("Created beads issue: {}", stdout.trim());
    } else {
        let stderr = String::from_utf8_lossy(&output.stderr);
        anyhow::bail!("bd create failed: {}", stderr);
    }
    
    Ok(())
}

async fn create_markdown_issue(
    analysis: &analyzer::Analysis,
    video_path: &std::path::Path,
    timestamp: &str,
) -> Result<()> {
    let filename = format!("issue-{}.md", timestamp);
    let content = format_issue_markdown(analysis, video_path);
    
    tokio::fs::write(&filename, &content).await?;
    println!("Created issue file: {}", filename);
    
    Ok(())
}

fn format_issue_body(analysis: &analyzer::Analysis, video_path: &std::path::Path) -> String {
    let mut body = String::new();
    
    body.push_str(&analysis.summary);
    body.push_str("\n\n## Steps to Reproduce\n\n");
    
    for (i, step) in analysis.steps.iter().enumerate() {
        body.push_str(&format!("{}. {}\n", i + 1, step));
    }
    
    if !analysis.timestamps.is_empty() {
        body.push_str("\n## Timestamps\n\n");
        for ts in &analysis.timestamps {
            if ts.description.is_empty() {
                body.push_str(&format!("- {}\n", ts.time));
            } else {
                body.push_str(&format!("- **{}** - {}\n", ts.time, ts.description));
            }
        }
    }
    
    body.push_str(&format!("\n## Recording\n\n`{}`\n", video_path.display()));
    
    body
}

fn format_issue_markdown(analysis: &analyzer::Analysis, video_path: &std::path::Path) -> String {
    let mut md = String::new();
    
    md.push_str(&format!("# {}\n\n", analysis.title));
    md.push_str(&format!("{}\n\n", analysis.summary));
    
    md.push_str("## Steps to Reproduce\n\n");
    for (i, step) in analysis.steps.iter().enumerate() {
        md.push_str(&format!("{}. {}\n", i + 1, step));
    }
    
    if !analysis.timestamps.is_empty() {
        md.push_str("\n## Timestamps\n\n");
        for ts in &analysis.timestamps {
            if ts.description.is_empty() {
                md.push_str(&format!("- {}\n", ts.time));
            } else {
                md.push_str(&format!("- **{}** - {}\n", ts.time, ts.description));
            }
        }
    }
    
    md.push_str(&format!("\n## Recording\n\n`{}`\n", video_path.display()));
    
    md
}
