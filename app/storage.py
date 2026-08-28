import os
import uuid
import io
from abc import ABC, abstractmethod
from typing import BinaryIO, Optional, Tuple
from PIL import Image, ImageOps


class StorageService(ABC):
    """Abstract interface for file storage (local or cloud S3-compatible)."""

    @abstractmethod
    def save(self, file_data: bytes | BinaryIO, filename: str, subfolder: str = 'private_images') -> str:
        """Save a file and return its storage identifier/path."""
        pass

    @abstractmethod
    def get(self, storage_id: str) -> Optional[bytes]:
        """Retrieve file content bytes."""
        pass

    @abstractmethod
    def delete(self, storage_id: str) -> bool:
        """Delete file from storage. Returns True if deleted or did not exist."""
        pass

    @abstractmethod
    def exists(self, storage_id: str) -> bool:
        """Check if file exists in storage."""
        pass

    @abstractmethod
    def get_absolute_path(self, storage_id: str) -> Optional[str]:
        """Get absolute path if local, or None if remote."""
        pass


class LocalStorageService(StorageService):
    """Secure Local Disk Storage Implementation."""

    def __init__(self, base_dir: str):
        self.base_dir = os.path.abspath(base_dir)
        self.private_dir = os.path.join(self.base_dir, 'private_images')
        self.avatar_dir = os.path.join(self.base_dir, 'avatars')
        os.makedirs(self.private_dir, exist_ok=True)
        os.makedirs(self.avatar_dir, exist_ok=True)

    def _resolve_path(self, storage_id: str) -> str:
        # Prevent directory traversal attacks
        clean_id = os.path.normpath(storage_id).lstrip('/\\')
        full_path = os.path.abspath(os.path.join(self.base_dir, clean_id))
        if not full_path.startswith(self.base_dir):
            raise ValueError("Security exception: Path traversal attempt detected.")
        return full_path

    def save(self, file_data: bytes | BinaryIO, filename: str, subfolder: str = 'private_images') -> str:
        target_dir = os.path.join(self.base_dir, subfolder)
        os.makedirs(target_dir, exist_ok=True)

        # Generate unique unguessable filename
        ext = os.path.splitext(filename)[1].lower()
        if not ext or ext not in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
            ext = '.jpg'

        secure_filename = f"{uuid.uuid4().hex}{ext}"
        storage_id = os.path.join(subfolder, secure_filename)
        dest_path = os.path.join(target_dir, secure_filename)

        if isinstance(file_data, bytes):
            with open(dest_path, 'wb') as f:
                f.write(file_data)
        else:
            file_data.seek(0)
            with open(dest_path, 'wb') as f:
                f.write(file_data.read())

        return storage_id

    def get(self, storage_id: str) -> Optional[bytes]:
        try:
            full_path = self._resolve_path(storage_id)
            if os.path.isfile(full_path):
                with open(full_path, 'rb') as f:
                    return f.read()
            return None
        except Exception:
            return None

    def delete(self, storage_id: str) -> bool:
        if not storage_id:
            return True
        try:
            full_path = self._resolve_path(storage_id)
            if os.path.isfile(full_path):
                os.remove(full_path)
            return True
        except Exception:
            return False

    def exists(self, storage_id: str) -> bool:
        if not storage_id:
            return False
        try:
            full_path = self._resolve_path(storage_id)
            return os.path.isfile(full_path)
        except Exception:
            return False

    def get_absolute_path(self, storage_id: str) -> Optional[str]:
        if not storage_id:
            return None
        try:
            full_path = self._resolve_path(storage_id)
            return full_path if os.path.isfile(full_path) else None
        except Exception:
            return None


class StorageServiceProxy(StorageService):
    """Dynamic proxy for StorageService singleton."""

    def __init__(self, backend: Optional[StorageService] = None):
        self._impl = backend

    def init_app(self, app):
        storage_dir = app.config.get('STORAGE_DIR', 'storage')
        self._impl = LocalStorageService(storage_dir)

    def set_backend(self, backend: StorageService):
        self._impl = backend

    def save(self, file_data: bytes | BinaryIO, filename: str, subfolder: str = 'private_images') -> str:
        if not self._impl:
            raise RuntimeError("StorageService is not initialized.")
        return self._impl.save(file_data, filename, subfolder)

    def get(self, storage_id: str) -> Optional[bytes]:
        if not self._impl:
            return None
        return self._impl.get(storage_id)

    def delete(self, storage_id: str) -> bool:
        if not self._impl:
            return True
        return self._impl.delete(storage_id)

    def exists(self, storage_id: str) -> bool:
        if not self._impl:
            return False
        return self._impl.exists(storage_id)

    def get_absolute_path(self, storage_id: str) -> Optional[str]:
        if not self._impl:
            return None
        return self._impl.get_absolute_path(storage_id)


def sanitize_and_process_image(
    file_stream_or_bytes: BinaryIO | bytes,
    max_dimension: int = 1920,
    is_avatar: bool = False
) -> Tuple[bytes, str, str]:
    """
    Validate, sanitize, strip metadata (EXIF for privacy), and re-encode image.
    Returns (cleaned_bytes, extension, mime_type).
    Raises ValueError if invalid or malicious image.
    """
    if hasattr(file_stream_or_bytes, 'read'):
        raw_bytes = file_stream_or_bytes.read()
    elif isinstance(file_stream_or_bytes, bytes):
        raw_bytes = file_stream_or_bytes
    else:
        raise ValueError("Invalid file input type.")

    if not raw_bytes:
        raise ValueError("Image data cannot be empty.")

    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            # Verify image integrity
            img.verify()

        # Re-open after verify()
        with Image.open(io.BytesIO(raw_bytes)) as img:
            orig_format = (img.format or 'JPEG').upper()
            if orig_format not in ('JPEG', 'JPG', 'PNG', 'WEBP', 'GIF'):
                raise ValueError("Unsupported image format. Allowed: JPEG, PNG, WEBP, GIF.")

            # Handle orientation from EXIF before stripping
            img = ImageOps.exif_transpose(img)

            # Resize if avatar or oversized
            if is_avatar:
                img = ImageOps.fit(img, (400, 400), Image.Resampling.LANCZOS)
            else:
                img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

            output = io.BytesIO()
            if orig_format in ('JPEG', 'JPG') or img.mode in ('RGB', 'CMYK'):
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                img.save(output, format='JPEG', quality=85, optimize=True)
                return output.getvalue(), '.jpg', 'image/jpeg'
            elif orig_format == 'WEBP':
                if img.mode in ('RGBA', 'LA'):
                    img.save(output, format='WEBP', quality=85, method=6)
                else:
                    img = img.convert('RGB')
                    img.save(output, format='WEBP', quality=85, method=6)
                return output.getvalue(), '.webp', 'image/webp'
            elif orig_format == 'GIF':
                img.save(output, format='GIF', optimize=True)
                return output.getvalue(), '.gif', 'image/gif'
            else:
                # Default to PNG
                img.save(output, format='PNG', optimize=True)
                return output.getvalue(), '.png', 'image/png'
    except Exception as e:
        raise ValueError(f"Invalid image file: {str(e)}")
