import Button from '@app/components/Common/Button';
import RequestModal from '@app/components/RequestModal';
import { Permission, useUser } from '@app/hooks/useUser';
import { PlayIcon } from '@heroicons/react/24/solid';
import { MediaStatus } from '@server/constants/media';
import type Media from '@server/entity/Media';
import axios from 'axios';
import { useState } from 'react';

interface Props {
  mediaType: 'movie' | 'tv';
  tmdbId: number;
  media?: Media;
}

const WatchNowButton = ({ mediaType, tmdbId, media }: Props) => {
  const [requesting, setRequesting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const { hasPermission } = useUser();
  const status = media?.status ?? MediaStatus.UNKNOWN;
  const needsRequest = [MediaStatus.UNKNOWN, MediaStatus.DELETED].includes(status);
  const canRequest = hasPermission(
    [Permission.REQUEST, mediaType === 'movie' ? Permission.REQUEST_MOVIE : Permission.REQUEST_TV],
    { type: 'or' }
  );
  if (status === MediaStatus.BLACKLISTED || (needsRequest && !canRequest)) {
    return null;
  }
  const watch = () => {
    const url = new URL(window.location.href);
    url.port = '8090';
    url.pathname = `/watch/${mediaType}/${tmdbId}`;
    url.search = '';
    url.hash = '';
    window.location.assign(url.href);
  };
  const start = async () => {
    setError('');
    if (!needsRequest) return watch();
    if (mediaType === 'tv') return setRequesting(true);
    setBusy(true);
    try {
      // Use Jellyseerr's authenticated API and configured defaults. The server
      // still enforces quotas, permissions, approval, and duplicate requests.
      await axios.post('/api/v1/request', {
        mediaType: 'movie', mediaId: tmdbId, is4k: false,
      });
      watch();
    } catch {
      setError('Could not request this movie. Use the Request button to check availability and settings.');
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <Button
        buttonType="primary"
        className="mr-2"
        data-testid="netfelix-watch-now"
        disabled={busy}
        onClick={start}
      >
        <PlayIcon />
        <span>{busy ? 'Starting…' : 'Watch now'}</span>
      </Button>
      {error && <span role="alert" className="mr-2 text-sm text-red-300">{error}</span>}
      <RequestModal
        show={requesting}
        type={mediaType}
        tmdbId={tmdbId}
        onCancel={() => setRequesting(false)}
        onComplete={(newStatus) => {
          setRequesting(false);
          if (newStatus !== MediaStatus.UNKNOWN && newStatus !== MediaStatus.DELETED) {
            watch();
          }
        }}
      />
    </>
  );
};

export default WatchNowButton;
