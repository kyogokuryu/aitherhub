import './App.css'
import MainLayout from './layouts/MainLayout'
import { Toaster } from "./components/ui/toaster";
import { BrowserRouter, Routes, Route } from 'react-router-dom';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainLayout />} />
        <Route path="/video/:videoId" element={<MainLayout />} />
      </Routes>
      <Toaster />
    </BrowserRouter>
  )
}
export default App
