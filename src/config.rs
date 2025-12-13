use anyhow::Result;
use std::path::PathBuf;
use std::sync::OnceLock;

static GEMINI_API_KEY: OnceLock<Option<String>> = OnceLock::new();

pub fn load() -> Result<()> {
    // Load from ~/.config/ayeye/.env
    if let Some(proj_dirs) = directories::ProjectDirs::from("", "", "ayeye") {
        let env_file = proj_dirs.config_dir().join(".env");
        if env_file.exists() {
            dotenvy::from_path(&env_file).ok();
        }
    }
    
    // Also try current directory
    dotenvy::dotenv().ok();
    
    GEMINI_API_KEY.get_or_init(|| std::env::var("GEMINI_API_KEY").ok());
    
    Ok(())
}

pub fn gemini_api_key() -> Option<&'static str> {
    GEMINI_API_KEY.get().and_then(|o| o.as_deref())
}

pub fn recordings_dir() -> Result<PathBuf> {
    if let Ok(dir) = std::env::var("AYEYE_RECORDINGS_DIR") {
        return Ok(PathBuf::from(dir));
    }
    
    directories::UserDirs::new()
        .and_then(|d| d.video_dir().map(|v| v.join("AyEye")))
        .ok_or_else(|| anyhow::anyhow!("Could not determine video directory"))
}
