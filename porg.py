from dataclasses import dataclass
from datetime import datetime
import hashlib
import mimetypes
import os.path

import exifread
import mutagen


# Config
SOURCE_PATH = '/Volumes/MEDIA/Photos'
TARGET_PATH = '/Volumes/MEDIA/Pictures'

# Globals
file_list = []


@dataclass
class File:
    path: str

    @property
    def type(self):
        """Retrieves the file mimetype by extension"""
        if not getattr(self, '_type', False):
            self._type, _ = mimetypes.guess_type(self.path)
            if not self._type:
                print(f"Can't guess type of file {self.path}")
        return self._type

    @property
    def is_image(self):
        return 'image' in self.type

    @property
    def is_video(self):
        return 'video' in self.type

    @property
    def exif(self):
        """
        Retrieve EXIF data from the file and merge it with wathever mutagen finds in there for video files.
        """
        if not getattr(self, '_exif', False):
            self._exif = exifread.process_file(open(self.path, 'rb'))
            if self.is_video:
                self._exif.update(mutagen.File(self.path))
        return self._exif

    @property
    def datetime(self):
        """
        Retrieves original creation date for the picture trying exif data first, filename guessing and finally
        modification date. Make sure your pictures are exported unmodified so the file attributes maintain their
        original values for this to work.
        """
        if self.is_image:
            date, time = self.exif['EXIF DateTimeOriginal'].values.split()
            return datetime(*(int(x) for x in date.split(':') + time.split(':')))

        if self.is_video:
            # Apple iPhone tag
            try:
                return datetime.strptime(self.exif.get('©day')[0], '%Y-%m-%dT%H:%M:%S%z')
            except TypeError:
                pass

        # Tag not found, try to guess datetime from filename
        # Format: YYYY-MM-DD HH.MM.SS.ext
        try:
            name, _ = os.path.basename(self.path).rsplit('.', maxsplit=1)
            date, time = name.split(' ')
            return datetime(*(int(x) for x in date.split('-') + time.split('.')))
        except ValueError:
            raise

        # Last resort, use file creation/modification date
        stat = os.stat(self.path)
        try:
            return stat.st_birthtime
        except AttributeError:
            # Linux: No easy way to get creation dates here,
            # so we'll settle for when its content was last modified.
            return stat.st_mtime

    @property
    def checksum(self):
        if not getattr(self, '_checksum', False):
            digest = hashlib.sha1()
            with open(self.path, 'rb') as handler:
                digest.update(handler.read())

            self._checksum = digest.hexdigest()
        return self._checksum


def read_path():
    for path, directories, files in os.walk(SOURCE_PATH):
        for filename in files:
            if not filename.startswith('.') and filename not in ['.', '..']:
                yield File(path=os.path.join(path, filename))


def get_target_path(fileobj):
    return os.path.join(TARGET_PATH, str(fileobj.datetime.year), '%02d' % fileobj.datetime.month)


if __name__ == '__main__':
    for fileobj in read_path():
        target_path = get_target_path(fileobj)
        os.makedirs(target_path, exist_ok=True)