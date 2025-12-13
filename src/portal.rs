use anyhow::{anyhow, Result};
use ashpd::desktop::screencast::{CursorMode, Screencast, SourceType};
use ashpd::desktop::PersistMode;
use ashpd::enumflags2::BitFlags;

/// Request screencast access via XDG Desktop Portal.
/// Returns the PipeWire node ID for the selected screen/window.
pub async fn request_screencast() -> Result<u32> {
    let proxy = Screencast::new().await?;
    
    // Create a session
    let session = proxy.create_session().await?;
    
    // Select sources - this shows the system dialog
    proxy
        .select_sources(
            &session,
            CursorMode::Embedded,
            BitFlags::from(SourceType::Monitor) | SourceType::Window,
            false, // multiple
            None,  // restore_token
            PersistMode::ExplicitlyRevoked,
        )
        .await?;
    
    // Start the screencast - None for window identifier on Wayland
    let response = proxy
        .start(&session, None)
        .await?
        .response()?;
    
    // Get the first stream's node ID
    let stream = response
        .streams()
        .first()
        .ok_or_else(|| anyhow!("No streams returned from portal"))?;
    
    Ok(stream.pipe_wire_node_id())
}
