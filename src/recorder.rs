use anyhow::Result;
use gstreamer as gst;
use gstreamer::prelude::*;
use std::path::Path;
use std::sync::Arc;
use tokio::sync::Notify;

pub async fn record(node_id: u32, output_path: &Path, stop_signal: Arc<Notify>) -> Result<()> {
    gst::init()?;
    
    // Use MKV - reliable EOS handling, then convert to MP4 for Gemini
    let output_str = output_path.display().to_string();
    
    let pipeline_str = format!(
        "pipewiresrc path={node_id} do-timestamp=true ! \
         videoconvert ! \
         x264enc tune=zerolatency speed-preset=ultrafast bitrate=2000 key-int-max=30 ! \
         queue max-size-buffers=100 ! \
         matroskamux name=mux streamable=true ! \
         filesink location=\"{output_str}\" \
         pulsesrc ! \
         audioconvert ! \
         opusenc bitrate=128000 ! \
         queue max-size-buffers=100 ! mux."
    );
    
    let pipeline = gst::parse::launch(&pipeline_str)?
        .downcast::<gst::Pipeline>()
        .map_err(|_| anyhow::anyhow!("Failed to create pipeline"))?;
    
    // Start playing
    pipeline.set_state(gst::State::Playing)?;
    
    // Wait for pipeline to reach playing state
    let bus = pipeline.bus().ok_or_else(|| anyhow::anyhow!("Failed to get bus"))?;
    
    // Check that we actually started playing
    let state_change_result = pipeline.state(gst::ClockTime::from_seconds(10));
    if state_change_result.1 != gst::State::Playing {
        return Err(anyhow::anyhow!("Pipeline failed to reach Playing state"));
    }
    
    // Wait for first frames to actually arrive from PipeWire
    // The pipeline is "playing" but PipeWire may not be sending frames yet
    eprintln!("Waiting for video stream...");
    
    let pipeline_for_wait = pipeline.clone();
    let bus_for_wait = bus.clone();
    
    tokio::task::spawn_blocking(move || -> Result<()> {
        // Wait for stream-start or first buffer by monitoring bus messages
        // and checking pipeline position
        let start = std::time::Instant::now();
        let timeout = std::time::Duration::from_secs(10);
        
        loop {
            if start.elapsed() > timeout {
                return Err(anyhow::anyhow!("Timeout waiting for video stream"));
            }
            
            // Check for any errors
            if let Some(msg) = bus_for_wait.timed_pop(gst::ClockTime::from_mseconds(100)) {
                match msg.view() {
                    gst::MessageView::Error(e) => {
                        return Err(anyhow::anyhow!("Pipeline error: {:?}", e.error()));
                    }
                    gst::MessageView::StreamStart(_) => {
                        // Stream has started
                        break;
                    }
                    _ => {}
                }
            }
            
            // Check if we have a valid position (means frames are flowing)
            if let Some(pos) = pipeline_for_wait.query_position::<gst::ClockTime>() {
                if pos > gst::ClockTime::ZERO {
                    break;
                }
            }
        }
        
        // Give a little extra time for the stream to stabilize
        std::thread::sleep(std::time::Duration::from_millis(500));
        
        Ok(())
    }).await??;
    
    eprintln!("Recording started!");
    
    // Clone for the blocking task
    let pipeline_clone = pipeline.clone();
    let bus_clone = bus.clone();
    
    // Wait for stop signal
    stop_signal.notified().await;
    
    eprintln!("Stop signal received, sending EOS...");
    
    // Send EOS and handle cleanup in a blocking task to avoid async issues
    let result = tokio::task::spawn_blocking(move || -> Result<()> {
        // Send EOS event
        pipeline_clone.send_event(gst::event::Eos::new());
        
        // Wait for EOS to propagate through the pipeline
        // This is crucial for proper file finalization
        for msg in bus_clone.iter_timed(gst::ClockTime::from_seconds(10)) {
            match msg.view() {
                gst::MessageView::Eos(_) => {
                    eprintln!("EOS received, finalizing...");
                    break;
                }
                gst::MessageView::Error(e) => {
                    let err = e.error();
                    let debug = e.debug();
                    eprintln!("GStreamer error during shutdown: {:?} ({:?})", err, debug);
                    break;
                }
                gst::MessageView::StateChanged(s) => {
                    if s.src().map(|s| s == pipeline_clone.upcast_ref::<gst::Object>()).unwrap_or(false) {
                        eprintln!("State changed to: {:?}", s.current());
                    }
                }
                _ => {}
            }
        }
        
        // Set to NULL to fully release resources
        pipeline_clone.set_state(gst::State::Null)?;
        
        Ok(())
    }).await?;
    
    result?;
    
    eprintln!("Recording saved.");
    
    Ok(())
}
