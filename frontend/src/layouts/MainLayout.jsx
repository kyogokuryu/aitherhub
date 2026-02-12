import Sidebar from "../components/Sidebar";
import MainContent from '../components/MainContent';
import { useState, useCallback, useMemo, useEffect } from "react";
import { useParams, useNavigate } from 'react-router-dom';

const getUserFromStorage = () => {
  try {
    const stored = localStorage.getItem("user");
    return stored ? JSON.parse(stored) : { isLoggedIn: false };
  } catch {
    return { isLoggedIn: false };
  }
};

export default function MainLayout() {
  const { videoId } = useParams();
  const navigate = useNavigate();
  const [openSidebar, setOpenSidebar] = useState(false);
  const [selectedVideoId, setSelectedVideoId] = useState(videoId || null);
  const [user, setUser] = useState(getUserFromStorage);
  const [refreshKey, setRefreshKey] = useState(0);
  const [showFeedback, setShowFeedback] = useState(false);

  // Sync selectedVideoId when URL param changes
  useEffect(() => {
    if (videoId) {
      setSelectedVideoId(videoId);
      setShowFeedback(false);
    } else {
      setSelectedVideoId(null);
    }
  }, [videoId]);
  useEffect(() => {
    let scrollY;
    if (openSidebar) {
      scrollY = window.scrollY;

      Object.assign(document.body.style, {
        position: "fixed",
        top: `-${scrollY}px`,
        left: "0",
        right: "0",
        width: "100%",
        overflow: "hidden",
      });

      return () => {
        Object.assign(document.body.style, {
          position: "",
          top: "",
          left: "",
          right: "",
          width: "",
          overflow: "",
        });
        window.scrollTo(0, scrollY);
      };
    }
  }, [openSidebar]);

  const handleVideoSelect = useCallback((video) => {
    setShowFeedback(false);
    if (video?.id) {
      setSelectedVideoId(video.id);
      navigate(`/video/${video.id}`);
    }
    setOpenSidebar(false);
  }, [navigate]);

  const handleUserChange = useCallback((newUser) => {
    setUser(newUser);
    if (!newUser?.isLoggedIn) {
      setSelectedVideoId(null);
    }
  }, []);

  const handleCloseSidebar = useCallback(() => {
    setOpenSidebar(false);
  }, []);

  const handleOpenSidebar = useCallback(() => {
    setOpenSidebar(true);
  }, []);

  const handleNewAnalysis = useCallback(() => {
    setShowFeedback(false);
    setSelectedVideoId(null);
    navigate('/');
    setOpenSidebar(false);
  }, [navigate]);
  const handleShowFeedback = useCallback(() => {
    setShowFeedback(true);
    setSelectedVideoId(null);
    setOpenSidebar(false);
  }, []);

  const handleCloseFeedback = useCallback(() => {
    setShowFeedback(false);
  }, []);

  const handleUploadSuccess = useCallback((videoId) => {
    setRefreshKey(prev => prev + 1);
    if (videoId) {
      setShowFeedback(false);
      setSelectedVideoId(videoId);
      navigate(`/video/${videoId}`);
    }
  }, [navigate]);

  const sidebarProps = useMemo(() => ({
    isOpen: openSidebar,
    onClose: handleCloseSidebar,
    user,
    onVideoSelect: handleVideoSelect,
    onNewAnalysis: handleNewAnalysis,
    onShowFeedback: handleShowFeedback,
    onCloseFeedback: handleCloseFeedback,
    refreshKey,
    showFeedback,
    selectedVideo: selectedVideoId ? { id: selectedVideoId } : null,
  }), [openSidebar, handleCloseSidebar, user, handleVideoSelect, handleNewAnalysis, handleShowFeedback, handleCloseFeedback, refreshKey, selectedVideoId, showFeedback]);

  const mainContentProps = useMemo(() => ({
    onOpenSidebar: handleOpenSidebar,
    user,
    setUser: handleUserChange,
    onUploadSuccess: handleUploadSuccess,
    selectedVideoId,
    showFeedback,
    onCloseFeedback: handleCloseFeedback,
  }), [handleOpenSidebar, user, handleUserChange, handleUploadSuccess, selectedVideoId, showFeedback, handleCloseFeedback]);

  return (
    <div className="min-h-screen bg-gray-100 flex justify-center">
      <div className="w-full flex">

        <aside className="hidden xl:block w-[320px] max-w-[320px] min-w-[320px] bg-white text-black">
          <Sidebar {...sidebarProps} />
        </aside>

        <div className="xl:hidden">
          <Sidebar {...sidebarProps} />
        </div>

        <main className="w-full md:flex-1 gradient-liveboost text-white">
          <MainContent {...mainContentProps}>
          </MainContent>
        </main>
      </div>
    </div>
  );
}
