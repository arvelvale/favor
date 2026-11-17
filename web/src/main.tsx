import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// 只引入拉丁字符子集：中文回退到系统字体（苹方 / 鸿蒙 / 微软雅黑）
import '@fontsource/poppins/latin-400.css'
import '@fontsource/poppins/latin-500.css'
import '@fontsource/poppins/latin-600.css'
import '@fontsource/poppins/latin-700.css'
import App from './App'
import './styles.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
