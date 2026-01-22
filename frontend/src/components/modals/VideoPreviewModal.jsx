import { Dialog, DialogBackdrop, DialogPanel } from "@headlessui/react";
import { useEffect, useRef, useState } from "react";
import CloseSvg from "../../assets/icons/close.svg";

/**
 * Modal video preview that seeks to a specific start time.
 */
export default function VideoPreviewModal({ open, onClose, videoUrl, timeStart = 0, timeEnd = null }) {
  const videoRef = useRef(null);
  const hasSetupRef = useRef(false);
  const hasSeekedRef = useRef(false);
  const [isLoading, setIsLoading] = useState(true);
  const [playBlocked, setPlayBlocked] = useState(false);
  const [bufferedProgress, setBufferedProgress] = useState(0);
  const [showCustomLoading, setShowCustomLoading] = useState(true);
  const [videoEnded, setVideoEnded] = useState(false);
  const prevOpenRef = useRef(false);
  const prevVideoUrlRef = useRef(null);

  // Reset states when modal closes or URL changes
  useEffect(() => {
    const prevOpen = prevOpenRef.current;
    const prevVideoUrl = prevVideoUrlRef.current;

    // Reset when modal closes or video URL changes
    if ((!open && prevOpen) || (videoUrl !== prevVideoUrl)) {
      setIsLoading(true); // eslint-disable-line
      setPlayBlocked(false);
      setBufferedProgress(0);
      setShowCustomLoading(true); // Always show custom loading initially
      setVideoEnded(false); // Reset ended state
      hasSetupRef.current = false;
      hasSeekedRef.current = false;
    }

    prevOpenRef.current = open;
    prevVideoUrlRef.current = videoUrl;
  }, [open, videoUrl]);

  // Seek to start time when modal opens or URL changes
  useEffect(() => {

    // Skip if modal closed or no video
    if (!open || !videoUrl) {
      return;
    }

    const setupVideoSeekAndPlay = () => {
      const vid = videoRef.current;
      if (!vid || hasSetupRef.current) {
        return;
      }

      hasSetupRef.current = true;

      const seekAndPlay = async () => {
        try {
          // Show custom loading when starting seek/play process
          setShowCustomLoading(true);
          setIsLoading(true);

          // Only seek if we haven't seeked yet and current time is not at desired position
          const shouldSeek = !hasSeekedRef.current && Math.abs(vid.currentTime - timeStart) > 0.5;

          if (shouldSeek && timeStart !== null && timeStart !== undefined) {
            vid.currentTime = timeStart;
            hasSeekedRef.current = true;
          }

          // Try to play, handle promise rejection (autoPlay blocked)
          try {
            await vid.play();
            setPlayBlocked(false);
            setIsLoading(false);
            // Keep custom loading for a moment to show success, then hide
            setTimeout(() => setShowCustomLoading(false), 500);
          } catch {
            setPlayBlocked(true);
            setIsLoading(false);
            // Keep custom loading to show play button
            // Don't hide it automatically since user needs to interact
          }
        } catch (e) {
          console.error('❌ Error seeking video:', e);
          setIsLoading(false);
          setShowCustomLoading(false);
        }
      };

      const handleCanPlay = () => {
        // Skip if video has ended at timeEnd (prevent infinite loop)
        if (videoEnded) {
          return;
        }

        // Only seek if we haven't seeked yet
        if (!hasSeekedRef.current) {
          seekAndPlay();
        }
      };

      const handleLoadedMetadata = () => {
        // If video is already ready to play, seek immediately
        if (vid.readyState >= 3) { // HAVE_FUTURE_DATA or higher
          seekAndPlay();
        }
      };

      // Add event listeners
      vid.addEventListener("loadedmetadata", handleLoadedMetadata);
      vid.addEventListener("canplay", handleCanPlay);

      // Check current state
      if (vid.readyState >= 3) {
        seekAndPlay();
      } else if (vid.readyState >= 1) {
        // Metadata loaded but not ready to play yet
        handleLoadedMetadata();
      }

      return () => {
        vid.removeEventListener("loadedmetadata", handleLoadedMetadata);
        vid.removeEventListener("canplay", handleCanPlay);
      };
    };

    // Try to setup immediately if video element exists
    const cleanup = setupVideoSeekAndPlay();

    // If setup failed (video element not ready), try again after a short delay
    if (!hasSetupRef.current) {
      const timeoutId = setTimeout(() => {
        if (open && videoUrl && !hasSetupRef.current) {
          setupVideoSeekAndPlay();
        }
      }, 100);

      return () => {
        clearTimeout(timeoutId);
        if (cleanup) cleanup();
      };
    }

    return () => {
      if (cleanup) cleanup();
    };
  }, [videoUrl, timeStart, timeEnd, open, videoEnded]);

  const handleTimeUpdate = (e) => {
    if (!timeEnd) return;
    try {
      if (e.currentTarget.currentTime >= timeEnd) {
        e.currentTarget.currentTime = timeEnd;
        e.currentTarget.pause();
        setVideoEnded(true); // Mark video as ended to prevent infinite canplay loops
      }
    } catch {
      // ignore
    }
  };

  const handleManualPlay = async () => {
    if (!videoRef.current) return;

    try {
      setIsLoading(true);
      await videoRef.current.play();
      setPlayBlocked(false);
      setIsLoading(false);
      // Hide custom loading after successful manual play
      setTimeout(() => setShowCustomLoading(false), 500);
    } catch (error) {
      console.error('Manual play failed:', error);
      setPlayBlocked(true);
      setIsLoading(false);
    }
  };

  const handleProgress = () => {
    const video = videoRef.current;
    if (!video || video.duration === 0) return;

    // Calculate buffered progress within preview range
    const currentTime = video.currentTime;
    const previewStart = timeStart || 0;
    const previewEnd = timeEnd || video.duration;

    // Find the buffered range that covers current position
    let bufferedEnd = 0;
    for (let i = 0; i < video.buffered.length; i++) {
      const start = video.buffered.start(i);
      const end = video.buffered.end(i);
      if (currentTime >= start && currentTime <= end) {
        bufferedEnd = end;
        break;
      }
    }

    // Calculate progress within preview range (0-100%)
    const previewDuration = previewEnd - previewStart;
    const bufferedInPreview = Math.min(bufferedEnd, previewEnd) - previewStart;
    const progress = Math.max(0, Math.min(100, (bufferedInPreview / previewDuration) * 100));

    setBufferedProgress(progress);
  };

  return (
    <Dialog open={open} onClose={onClose} className="relative z-50">
      <DialogBackdrop className="fixed inset-0 bg-black/60 transition-opacity" />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-3">
        <DialogPanel className="relative w-full max-w-5xl rounded-xl overflow-hidden bg-black shadow-2xl">
          <button
            onClick={onClose}
            className="absolute right-3 top-3 z-10 w-10 h-10 rounded-full bg-white/80 hover:bg-white transition flex items-center justify-center cursor-pointer"
          >
            <img src={CloseSvg} alt="Close" className="w-4 h-4" />
          </button>
          {videoUrl ? (
            <div className="relative w-full h-full bg-black aspect-video">
              <video
                ref={videoRef}
                key={videoUrl}
                src={videoUrl}
                controls={!playBlocked && !showCustomLoading && !isLoading}
                autoPlay
                muted
                playsInline
                preload="metadata"
                poster="" // Disable default poster/loading
                className="w-full h-full"
                style={{ backgroundColor: 'black' }} // Prevent flash of white
                onTimeUpdate={handleTimeUpdate}
                onProgress={(e) => {
                  handleProgress();
                  const video = e.target;
                  const buffered = video.buffered.length > 0 ? video.buffered.end(video.buffered.length - 1) : 0;
                  console.log(`📊 Progress - buffered: ${buffered.toFixed(1)}s / ${video.duration?.toFixed(1) || '?'}s`);
                }}
                onLoadStart={() => console.log('🎬 Video loadStart - enabling streaming mode')}
                onLoadedMetadata={() => console.log('📋 Metadata loaded - video ready for streaming')}
                onCanPlay={() => console.log('🎬 CanPlay - video buffered and ready')}
                onCanPlayThrough={() => console.log('🎬 CanPlayThrough - video fully buffered')}
                onEnded={() => setVideoEnded(true)}
                onError={(e) => console.error('Video error:', e)}
              />

              {/* Loading Overlay */}
              {isLoading && showCustomLoading && (
                <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                  <div className="flex flex-col items-center gap-3">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white"></div>
                    <div className="flex flex-col items-center gap-2">
                      <p className="text-white text-sm">動画を準備中...</p>
                      {bufferedProgress > 0 && (
                        <div className="w-48 bg-gray-700 rounded-full h-1.5">
                          <div
                            className="bg-purple-500 h-1.5 rounded-full transition-all duration-300"
                            style={{ width: `${bufferedProgress}%` }}
                          />
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Play Blocked Overlay */}
              {playBlocked && !isLoading && (
                <div className="absolute inset-0 bg-black/70 flex items-center justify-center">
                  <div className="flex flex-col items-center gap-4">
                    <div className="text-white text-center">
                      <p className="text-lg mb-2">再生するにはクリックしてください</p>
                      <p className="text-sm text-gray-300">ブラウザの自動再生ポリシーにより停止されました</p>
                    </div>
                    <button
                      onClick={handleManualPlay}
                      className="px-6 py-3 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
                    >
                      <span>▶️</span>
                      再生する
                    </button>
                  </div>
                </div>
              )}

              {/* Video Ended Overlay */}
              {videoEnded && !isLoading && (
                <div className="absolute inset-0 bg-black/70 flex items-center justify-center">
                  <div className="flex flex-col items-center gap-4">
                    <div className="text-white text-center">
                      <p className="text-lg mb-2">動画が終了しました</p>
                      <p className="text-sm text-gray-300">プレビューを終了します</p>
                    </div>
                    <div className="flex gap-3">
                      <button
                        onClick={() => {
                          setVideoEnded(false);
                          hasSeekedRef.current = false; // Allow replay
                          if (videoRef.current) {
                            videoRef.current.currentTime = timeStart || 0;
                            videoRef.current.play().catch(() => {
                              setPlayBlocked(true);
                            });
                          }
                        }}
                        className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
                      >
                        <span>🔄</span>
                        もう一度見る
                      </button>
                      <button
                        onClick={onClose}
                        className="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg font-medium transition-colors"
                      >
                        閉じる
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="w-full aspect-video flex items-center justify-center text-white/80">
              プレビューを読み込み中...
            </div>
          )}
        </DialogPanel>
      </div>
    </Dialog>
  );
}

