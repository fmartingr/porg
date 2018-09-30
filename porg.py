from dataclasses import dataclass
from datetime import datetime
import hashlib
import mimetypes
import os.path
import shutil
import subprocess
from typing import Text

import mutagen


# Config
SOURCE_PATH = '/Volumes/MEDIA/Photos'
TARGET_PATH = '/Volumes/MEDIA/Pictures'
CUSTOM_MIMETYPES = {
    # RAW pictures
    'ARW': 'image/x-sony-arw',
    'CR2': 'image/x-canon-cr2',
    'CRW': 'image/x-canon-crw',
    'DCR': 'image/x-kodak-dcr',
    'DNG': 'image/x-adobe-dng',
    'ERF': 'image/x-epson-erf',
    'K25': 'image/x-kodak-k25',
    'KDC': 'image/x-kodak-kdc',
    'MRW': 'image/x-minolta-mrw',
    'NEF': 'image/x-nikon-nef',
    'ORF': 'image/x-olympus-orf',
    'PEF': 'image/x-pentax-pef',
    'RAF': 'image/x-fuji-raf',
    'RAW': 'image/x-panasonic-raw',
    'SR2': 'image/x-sony-sr2',
    'SRF': 'image/x-sony-srf',
    'X3F': 'image/x-sigma-x3f',
    # High Efficiency Image/Video
    'HEIC': 'image/heic',
    'HEIF': 'image/heif',
    'HEVC': 'video/hevc',
}
for extension, mimetype in CUSTOM_MIMETYPES.items():
    mimetypes.add_type(mimetype, f'.{extension}')
    mimetypes.add_type(mimetype, f'.{extension.lower()}')

# Globals
file_list = []


def read_exif(path):
    output = {}
    with subprocess.Popen(['exiftool', path], stdout=subprocess.PIPE) as proc:
        for line in proc.stdout.readlines():
            key, value = line.decode('utf-8').strip().split(':', maxsplit=1)
            output[key.strip()] = value.strip()
    return output


@dataclass
class File:
    path: str

    @property
    def type(self) -> Text:
        """Retrieves the file mimetype by extension"""
        if not getattr(self, '_type', False):
            self._type, _ = mimetypes.guess_type(self.path)
            if not self._type:
                print(f"Can't guess type of file {self.path}")
        return self._type

    @property
    def is_image(self) -> bool:
        return 'image' in self.type

    @property
    def is_video(self) -> bool:
        return 'video' in self.type

    @property
    def exif(self) -> dict:
        """
        Retrieve EXIF data from the file and merge it with wathever mutagen finds in there for video files.
        """
        if not getattr(self, '_exif', False):
            self._exif = read_exif(self.path)
            if self.is_video:
                self._exif.update(mutagen.File(self.path))
        return self._exif

    def get_datetime(self) -> datetime:
        """
        Retrieves original creation date for the picture trying exif data first, filename guessing and finally
        modification date. Make sure your pictures are exported unmodified so the file attributes maintain their
        original values for this to work.
        """

        CREATION_DATE_EXIF_KEYS = ('Content Create Date', 'Date/Time Original', 'Create Date', 'Date Created', )

        for key in CREATION_DATE_EXIF_KEYS:
            try:
                return datetime.strptime(self.exif[key], '%Y:%m:%d %H:%M:%S%z')
            except KeyError:
                pass
            except ValueError:
                try:
                    cleaned = self.exif[key].rsplit('.', maxsplit=1)
                    return datetime.strptime(cleaned[0], '%Y:%m:%d %H:%M:%S')
                except ValueError:
                    pass

        # Tag not found, try to guess from filename
        # Format: YYYY-MM-DD HH.MM.SS.ext
        try:
            name, _ = self.filename.rsplit('.', maxsplit=1)
            date, time = name.split(' ')
            return datetime(*(int(x) for x in date.split('-') + time.split('.')))
        except ValueError:
            pass

        print(f'---- Using stat data for {self.path}')
        for key, value in self.exif.items():
            if 'date' in key.lower() and 'file' not in key.lower():
                print(f' - found "{key}={value}"')

        # Last resort, use file creation/modification date
        stat = os.stat(self.path)
        try:
            return datetime.fromtimestamp(stat.st_birthtime)
        except AttributeError:
            # Linux: No easy way to get creation dates here,
            # so we'll settle for when its content was last modified.
            return datetime.fromtimestamp(stat.st_mtime)

    @property
    def datetime(self):
        if not getattr(self, '_datetime', False):
            self._datetime = self.get_datetime()
        return self._datetime

    @property
    def filename(self):
        return os.path.splitext(os.path.basename(self.path))[0]

    @property
    def extension(self):
        return os.path.splitext(self.path)[1][1:].lower()

    @property
    def checksum(self) -> Text:
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
        try:
            target_path = get_target_path(fileobj)
        except Exception as exc:
            print(f'---- Error on {fileobj.path} ----')
            raise exc
        new_filename = '.'.join([fileobj.datetime.strftime('%Y-%m-%d_%H-%M-%S'), fileobj.extension])
        os.makedirs(target_path, exist_ok=True)
        shutil.move(fileobj.path, os.path.join(target_path, new_filename))
