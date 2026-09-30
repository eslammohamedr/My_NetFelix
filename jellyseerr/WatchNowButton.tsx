import Button from '@app/components/Common/Button';
import RequestModal from '@app/components/RequestModal';
import { Permission, useUser } from '@app/hooks/useUser';
import { BoltIcon, PlayIcon, SparklesIcon } from '@heroicons/react/24/solid';
import { MediaStatus } from '@server/constants/media';
import type Media from '@server/entity/Media';
import axios from 'axios';
import { useState } from 'react';

interface Props {
  mediaType: 'movie' | 'tv';
  tmdbId: number;
  media?: Media;
  title?: string;
}

const WatchNowButton = ({ mediaType, tmdbId, media, title }: Props) => {
  const [requesting, setRequesting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  // AI Download state
  const [aiBusy, setAiBusy] = useState(false);
  const [aiMessage, setAiMessage] = useState('');
  const [aiError, setAiError] = useState('');

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

  const requestAi = async (dubMode: 'auto' | 'egyptian') => {
    setAiBusy(true);
    setAiMessage('');
    setAiError('');
    try {
      const host = window.location.hostname || '127.0.0.1';
      const res = await axios.post(`http://${host}:8092/api/request`, {
        tmdbId,
        mediaType,
        title: title || '',
        dub: dubMode,
      }, { timeout: 10000 });

      if (res.data && res.data.message) {
        setAiMessage(res.data.message);
      } else {
        setAiMessage(dubMode === 'egyptian' ? 'تم استلام الطلب بالدبلجة المصرية!' : 'تم استلام طلب التحميل الذكي!');
      }
    } catch (err: any) {
      console.error('AI Request Error:', err);
      setAiError('تعذر الاتصال بـ NetFelix AI (تأكد من تشغيل الخدمة على 8092)');
    } finally {
      setAiBusy(false);
    }
  };

  const host = typeof window !== 'undefined' ? (window.location.hostname || '127.0.0.1') : '127.0.0.1';
  const studioUrl = `http://${host}:8092/`;

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

      <Button
        buttonType="warning"
        className="mr-2 border-0 bg-gradient-to-r from-indigo-600 to-purple-600 font-medium text-white shadow-md hover:from-indigo-700 hover:to-purple-700"
        data-testid="netfelix-ai-smart"
        disabled={aiBusy}
        onClick={() => requestAi('auto')}
        title="تحميل ذكي شامل (أعلى جودة + صوت أصلي أو ترجمة عربية تلقائية)"
      >
        <BoltIcon />
        <span>{aiBusy ? 'جاري الإرسال…' : '⚡ تحميل ذكي (AI Auto)'}</span>
      </Button>

      <Button
        buttonType="warning"
        className="mr-2 border-0 bg-gradient-to-r from-amber-500 to-amber-600 font-medium text-white shadow-md hover:from-amber-600 hover:to-amber-700"
        data-testid="netfelix-ai-egyptian"
        disabled={aiBusy}
        onClick={() => requestAi('egyptian')}
        title="تحميل بالدبلجة المصرية الأصلية (كلاسيكيات الكارتون والرسوم المتحركة)"
      >
        <SparklesIcon />
        <span>{aiBusy ? 'جاري الإرسال…' : '🇪🇬 دبلجة مصرية'}</span>
      </Button>

      <a
        href={studioUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="mr-2 inline-flex items-center gap-1 rounded-md border border-gray-600 bg-gray-800/80 px-3 py-1.5 text-xs font-semibold text-gray-200 shadow-sm transition hover:bg-gray-700 hover:text-white"
        title="فتح استوديو التحميل الشامل بالذكاء الاصطناعي (حَمّل أي رابط أو اسم مباشرة)"
      >
        <span>🤖 استوديو AI</span>
      </a>

      {aiMessage && (
        <span role="status" className="bg-green-950/60 mr-2 inline-block rounded border border-green-700 px-2 py-1 text-sm font-medium text-green-400">
          {aiMessage}
        </span>
      )}
      {aiError && (
        <span role="alert" className="bg-red-950/60 mr-2 inline-block rounded border border-red-700 px-2 py-1 text-sm text-red-300">
          {aiError}
        </span>
      )}
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
