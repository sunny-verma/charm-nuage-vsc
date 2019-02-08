import os
import urllib.request, urllib.error, urllib.parse
from urllib.request import urlretrieve
import urllib.parse
import hashlib

from charmhelpers.fetch import (
    BaseFetchHandler,
    UnhandledSource
)
from charmhelpers.payload.archive import (
    get_archive_handler,
    extract,
)
from charmhelpers.core.host import mkdir, check_hash


class ArchiveUrlFetchHandler(BaseFetchHandler):
    """
    Handler to download archive files from arbitrary URLs.

    Can fetch from http, https, ftp, and file URLs.

    Can install either tarballs (.tar, .tgz, .tbz2, etc) or zip files.

    Installs the contents of the archive in $CHARM_DIR/fetched/.
    """
    def can_handle(self, source):
        url_parts = self.parse_url(source)
        if url_parts.scheme not in ('http', 'https', 'ftp', 'file'):
            return "Wrong source type"
        if get_archive_handler(self.base_url(source)):
            return True
        return False

    def download(self, source, dest):
        """
        Download an archive file.

        :param str source: URL pointing to an archive file.
        :param str dest: Local path location to download archive file to.
        """
        # propogate all exceptions
        # URLError, OSError, etc
        proto, netloc, path, params, query, fragment = urllib.parse.urlparse(source)
        if proto in ('http', 'https'):
            auth, barehost = urllib.parse.splituser(netloc)
            if auth is not None:
                source = urllib.parse.urlunparse((proto, barehost, path, params, query, fragment))
                username, password = urllib.parse.splitpasswd(auth)
                passman = urllib.request.HTTPPasswordMgrWithDefaultRealm()
                # Realm is set to None in add_password to force the username and password
                # to be used whatever the realm
                passman.add_password(None, source, username, password)
                authhandler = urllib.request.HTTPBasicAuthHandler(passman)
                opener = urllib.request.build_opener(authhandler)
                urllib.request.install_opener(opener)
        response = urllib.request.urlopen(source)
        try:
            with open(dest, 'w') as dest_file:
                dest_file.write(response.read())
        except Exception as e:
            if os.path.isfile(dest):
                os.unlink(dest)
            raise e

    # Mandatory file validation via Sha1 or MD5 hashing.
    def download_and_validate(self, url, hashsum, validate="sha1"):
        tempfile, headers = urlretrieve(url)
        check_hash(tempfile, hashsum, validate)
        return tempfile

    def install(self, source, dest=None, checksum=None, hash_type='sha1'):
        """
        Download and install an archive file, with optional checksum validation.

        The checksum can also be given on the `source` URL's fragment.
        For example::

            handler.install('http://example.com/file.tgz#sha1=deadbeef')

        :param str source: URL pointing to an archive file.
        :param str dest: Local destination path to install to. If not given,
            installs to `$CHARM_DIR/archives/archive_file_name`.
        :param str checksum: If given, validate the archive file after download.
        :param str hash_type: Algorithm used to generate `checksum`.
            Can be any hash alrgorithm supported by :mod:`hashlib`,
            such as md5, sha1, sha256, sha512, etc.

        """
        url_parts = self.parse_url(source)
        dest_dir = os.path.join(os.environ.get('CHARM_DIR'), 'fetched')
        if not os.path.exists(dest_dir):
            mkdir(dest_dir, perms=0o755)
        dld_file = os.path.join(dest_dir, os.path.basename(url_parts.path))
        try:
            self.download(source, dld_file)
        except urllib.error.URLError as e:
            raise UnhandledSource(e.reason)
        except OSError as e:
            raise UnhandledSource(e.strerror)
        options = urllib.parse.parse_qs(url_parts.fragment)
        for key, value in list(options.items()):
            if key in hashlib.algorithms:
                check_hash(dld_file, value, key)
        if checksum:
            check_hash(dld_file, checksum, hash_type)
        return extract(dld_file, dest)
