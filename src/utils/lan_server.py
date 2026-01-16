"""
局域网空投服务 (V2.0)
在局域网内开启 HTTP 服务，生成二维码供手机扫码下载视频
"""
import http.server
import socketserver
import threading
import logging
import os
import functools
import urllib.parse
import qrcode
from io import BytesIO
from PyQt5.QtGui import QPixmap, QImage

logger = logging.getLogger(__name__)

class LanDropServer:
    """局域网文件传输服务"""
    
    def __init__(self, port=8000, directory="Output"):
        self.port = port
        self.directory = os.path.abspath(directory)
        self.httpd = None
        self.thread = None
        self.running = False

    def get_local_ip(self):
        """获取本机局域网 IP"""
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def start(self):
        """启动 HTTP 服务器"""
        if self.running:
            logger.warning("局域网服务已在运行")
            return False
        
        try:
            # 创建服务器（不要全局 chdir，避免影响整个应用）
            handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=self.directory)

            class _ThreadingTCPServer(socketserver.ThreadingTCPServer):
                allow_reuse_address = True
                daemon_threads = True

            self.httpd = _ThreadingTCPServer(("", int(self.port)), handler)
            
            # 在后台线程运行
            self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
            self.thread.start()
            
            self.running = True
            local_ip = self.get_local_ip()
            logger.info(f"[SERVER] 局域网服务已启动: http://{local_ip}:{self.port}")
            
            return True
            
        except Exception as e:
            logger.error(f"启动局域网服务失败: {e}")
            return False

    def stop(self):
        """停止服务器"""
        if not self.running:
            return
        
        if self.httpd:
            self.httpd.shutdown()
            try:
                self.httpd.server_close()
            except Exception:
                pass
            self.httpd = None
        
        self.running = False
        logger.info("[SERVER] 局域网服务已停止")

    def get_url(self):
        """返回访问地址"""
        if not self.running:
            return None
        return f"http://{self.get_local_ip()}:{self.port}"

    def generate_qrcode(self, file_name=None):
        """
        生成二维码（QPixmap 格式，可直接在 QLabel 中显示）
        file_name: 如果指定，则生成该文件的直达链接
        """
        if not self.running:
            return None
        
        try:
            base_url = self.get_url()
            if file_name:
                safe_name = urllib.parse.quote(str(file_name))
                url = f"{base_url}/{safe_name}"
            else:
                url = base_url
            
            # 生成二维码
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(url)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            # 转换为 QPixmap
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            
            qimage = QImage()
            qimage.loadFromData(buffer.getvalue())
            pixmap = QPixmap.fromImage(qimage)
            
            return pixmap
            
        except Exception as e:
            logger.error(f"生成二维码失败: {e}")
            return None

# 全局单例
_server_instance = None

def get_lan_server():
    """获取全局局域网服务实例"""
    global _server_instance
    if _server_instance is None:
        _server_instance = LanDropServer()
    return _server_instance
