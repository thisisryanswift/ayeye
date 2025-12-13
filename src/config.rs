use anyhow::Result;
use std::path::PathBuf;
use std::sync::OnceLock;

static GEMINI_API_KEY: OnceLock<Option<String>> = OnceLock::new();

pub fn load() -> Result<()> {
    // Load from ~/.config/ayeye/.env
    let config_dir = directories::ProjectDirs::from("", "", "ayeye")
        .map(|p| p.config_dir().to_path_buf())
        .unwrap_or_else(|| {
            directories::BaseDirs::new()
                .map(|d| d.config_dir().join("ayeye"))
                .unwrap_or_else(|| PathBuf::from("~/.config/ayeye"))
        });
    
    let env_file = config_dir.join(".env");
    if env_file.exists() {
        dotenvy::from_path(&env_file).ok();
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
    let dir = std::env::var("AYEYE_RECORDINGS_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            directories::UserDirs::new()
                .and_then(|d| d.video_dir().map(|v| v.join("AyEye")))
                .unwrap_or_else(|| PathBuf::from("~/Videos/AyEye"))
        });
    
    Ok(dir)
}
