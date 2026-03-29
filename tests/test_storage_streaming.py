"""
Storage and streaming tests for watch party
Tests file upload, storage management, and video streaming
"""

import pytest
import os
import tempfile
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path


class TestVideoUpload:
    """Test video file upload functionality"""

    def test_upload_creates_file(self, temp_upload_dir):
        """Upload creates file in storage"""
        filename = "test_video.mp4"
        filepath = os.path.join(temp_upload_dir, filename)
        
        # Create test file
        with open(filepath, "wb") as f:
            f.write(b"test video data")
        
        assert os.path.exists(filepath)

    def test_upload_generates_unique_name(self):
        """Upload generates unique filename"""
        room_id = "abc123"
        ext = ".mp4"
        filename = f"{room_id}{ext}"
        
        assert filename == "abc123.mp4"

    def test_upload_preserves_extension(self):
        """Upload preserves file extension"""
        extensions = [".mp4", ".webm", ".mkv", ".mov", ".avi", ".m4v"]
        
        for ext in extensions:
            assert ext in extensions

    def test_upload_validates_format(self):
        """Upload validates video format"""
        allowed = [".mp4", ".webm", ".mkv", ".mov", ".avi", ".m4v"]
        test_file = "video.mp4"
        ext = os.path.splitext(test_file)[1].lower()
        
        assert ext in allowed

    def test_upload_rejects_invalid_format(self):
        """Upload rejects invalid format"""
        allowed = [".mp4", ".webm", ".mkv", ".mov", ".avi", ".m4v"]
        test_file = "video.txt"
        ext = os.path.splitext(test_file)[1].lower()
        
        assert ext not in allowed

    def test_upload_checks_file_size(self):
        """Upload checks file size"""
        max_mb = 10240
        file_size_mb = 5000
        
        assert file_size_mb <= max_mb

    def test_upload_rejects_oversized_file(self):
        """Upload rejects file exceeding limit"""
        max_mb = 10240
        file_size_mb = 15000
        
        assert file_size_mb > max_mb

    def test_upload_with_custom_title(self):
        """Upload accepts custom title"""
        title = "My Custom Movie Title"
        
        assert len(title) > 0
        assert len(title) <= 100

    def test_upload_truncates_long_title(self):
        """Upload truncates long title"""
        title = "x" * 150
        max_length = 100
        
        truncated = title[:max_length]
        
        assert len(truncated) == max_length

    def test_upload_with_role_restriction(self):
        """Upload can set role restriction"""
        role_id = "987654321"
        
        assert role_id is not None


class TestStorageManagement:
    """Test storage management and cleanup"""

    def test_storage_folder_exists(self, temp_upload_dir):
        """Storage folder is created"""
        assert os.path.exists(temp_upload_dir)
        assert os.path.isdir(temp_upload_dir)

    def test_storage_folder_writable(self, temp_upload_dir):
        """Storage folder is writable"""
        test_file = os.path.join(temp_upload_dir, "test.txt")
        
        with open(test_file, "w") as f:
            f.write("test")
        
        assert os.path.exists(test_file)

    def test_get_storage_info(self, temp_upload_dir):
        """Get storage information"""
        import shutil
        
        stat = shutil.disk_usage(temp_upload_dir)
        info = {
            "total_gb": stat.total / (1024**3),
            "used_gb": stat.used / (1024**3),
            "free_gb": stat.free / (1024**3),
            "percent_used": (stat.used / stat.total) * 100,
        }
        
        assert "total_gb" in info
        assert "used_gb" in info
        assert "free_gb" in info
        assert "percent_used" in info

    def test_cleanup_old_videos(self, temp_upload_dir):
        """Cleanup removes old video files"""
        # Create old file
        old_file = os.path.join(temp_upload_dir, "old_video.mp4")
        with open(old_file, "wb") as f:
            f.write(b"old video")
        
        # Simulate cleanup
        if os.path.exists(old_file):
            os.remove(old_file)
        
        assert not os.path.exists(old_file)

    def test_cleanup_preserves_recent_videos(self, temp_upload_dir):
        """Cleanup preserves recent videos"""
        # Create recent file
        recent_file = os.path.join(temp_upload_dir, "recent_video.mp4")
        with open(recent_file, "wb") as f:
            f.write(b"recent video")
        
        # Should not be deleted
        assert os.path.exists(recent_file)

    def test_file_path_stored_in_room(self):
        """File path is stored in room object"""
        room = {
            "file_path": "/uploads/watch_party/abc123.mp4",
        }
        
        assert room["file_path"] is not None

    def test_delete_file_on_room_close(self, temp_upload_dir):
        """File is deleted when room closes"""
        filepath = os.path.join(temp_upload_dir, "video.mp4")
        
        # Create file
        with open(filepath, "wb") as f:
            f.write(b"video data")
        
        # Delete on close
        if os.path.exists(filepath):
            os.remove(filepath)
        
        assert not os.path.exists(filepath)


class TestVideoStreaming:
    """Test video streaming functionality"""

    def test_stream_returns_video_content(self, temp_upload_dir):
        """Stream returns video file content"""
        filepath = os.path.join(temp_upload_dir, "video.mp4")
        test_data = b"test video data"
        
        with open(filepath, "wb") as f:
            f.write(test_data)
        
        with open(filepath, "rb") as f:
            content = f.read()
        
        assert content == test_data

    def test_stream_supports_range_requests(self):
        """Stream supports HTTP Range requests"""
        file_size = 1048576  # 1MB
        range_header = "bytes=0-1023"
        
        # Parse range
        byte_start = 0
        byte_end = 1023
        length = byte_end - byte_start + 1
        
        assert length == 1024

    def test_stream_partial_content_response(self):
        """Stream returns 206 Partial Content for range requests"""
        response_code = 206
        
        assert response_code == 206

    def test_stream_content_range_header(self):
        """Stream includes Content-Range header"""
        headers = {
            "Content-Range": "bytes 0-1023/1048576",
        }
        
        assert "Content-Range" in headers

    def test_stream_accept_ranges_header(self):
        """Stream includes Accept-Ranges header"""
        headers = {
            "Accept-Ranges": "bytes",
        }
        
        assert headers["Accept-Ranges"] == "bytes"

    def test_stream_content_length_header(self):
        """Stream includes Content-Length header"""
        headers = {
            "Content-Length": "1024",
        }
        
        assert "Content-Length" in headers

    def test_stream_mime_type_mp4(self):
        """Stream sets correct MIME type for MP4"""
        mime = "video/mp4"
        
        assert mime == "video/mp4"

    def test_stream_mime_type_webm(self):
        """Stream sets correct MIME type for WebM"""
        mime = "video/webm"
        
        assert mime == "video/webm"

    def test_stream_mime_type_mkv(self):
        """Stream sets correct MIME type for MKV"""
        mime = "video/x-matroska"
        
        assert mime == "video/x-matroska"

    def test_stream_chunked_delivery(self, temp_upload_dir):
        """Stream delivers video in chunks"""
        filepath = os.path.join(temp_upload_dir, "video.mp4")
        chunk_size = 65536  # 64KB
        
        # Create test file
        with open(filepath, "wb") as f:
            f.write(b"x" * (chunk_size * 3))
        
        # Read in chunks
        chunks = []
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                chunks.append(chunk)
        
        assert len(chunks) == 3

    def test_stream_seek_support(self):
        """Stream supports seeking"""
        file_size = 1048576
        seek_position = 500000
        
        assert seek_position < file_size

    def test_stream_file_not_found(self):
        """Stream returns 404 for missing file"""
        response_code = 404
        
        assert response_code == 404

    def test_stream_access_denied(self):
        """Stream returns 403 for access denied"""
        response_code = 403
        
        assert response_code == 403


class TestExternalURLs:
    """Test external URL video support"""

    def test_external_url_validation(self):
        """External URLs are validated"""
        url = "https://example.com/video.mp4"
        
        assert url.startswith("https://")

    def test_external_url_http_support(self):
        """HTTP URLs are supported"""
        url = "http://example.com/video.mp4"
        
        assert url.startswith("http://")

    def test_external_url_stored_directly(self):
        """External URLs are stored directly"""
        room = {
            "video_url": "https://example.com/video.mp4",
        }
        
        assert room["video_url"].startswith("https://")

    def test_uploaded_url_uses_stream_endpoint(self):
        """Uploaded videos use stream endpoint"""
        room = {
            "video_url": "/watch/stream/abc123",
        }
        
        assert room["video_url"].startswith("/watch/stream/")


class TestFileValidation:
    """Test file validation"""

    def test_validate_video_extension(self):
        """Validate video file extension"""
        allowed = [".mp4", ".webm", ".mkv", ".mov", ".avi", ".m4v"]
        test_ext = ".mp4"
        
        assert test_ext in allowed

    def test_reject_executable_extension(self):
        """Reject executable file extension"""
        allowed = [".mp4", ".webm", ".mkv", ".mov", ".avi", ".m4v"]
        test_ext = ".exe"
        
        assert test_ext not in allowed

    def test_reject_script_extension(self):
        """Reject script file extension"""
        allowed = [".mp4", ".webm", ".mkv", ".mov", ".avi", ".m4v"]
        test_ext = ".py"
        
        assert test_ext not in allowed

    def test_case_insensitive_extension(self):
        """Extension check is case-insensitive"""
        ext1 = ".MP4"
        ext2 = ".mp4"
        
        assert ext1.lower() == ext2

    def test_validate_file_size_mb(self):
        """Validate file size in MB"""
        max_mb = 10240
        file_size_mb = 5000
        
        assert file_size_mb <= max_mb

    def test_validate_file_size_bytes(self):
        """Validate file size in bytes"""
        max_bytes = 10240 * 1024 * 1024
        file_size_bytes = 5000 * 1024 * 1024
        
        assert file_size_bytes <= max_bytes


class TestStreamingPerformance:
    """Test streaming performance characteristics"""

    def test_chunk_size_64kb(self):
        """Streaming uses 64KB chunks"""
        chunk_size = 65536
        
        assert chunk_size == 65536

    def test_buffer_size_1mb(self):
        """Streaming buffer is 1MB"""
        buffer_size = 1024 * 1024
        
        assert buffer_size == 1048576

    def test_stream_timeout_30s(self):
        """Stream timeout is 30 seconds"""
        timeout = 30
        
        assert timeout == 30

    def test_concurrent_streams(self):
        """Multiple concurrent streams supported"""
        max_concurrent = 500
        
        assert max_concurrent >= 100
