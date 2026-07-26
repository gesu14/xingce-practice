import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { QuizPlayer } from '../components/QuizPlayer';
import { getQuestions, getSprintPacks, getTips } from '../lib/data';
import { loadProgress, markSprintCleared } from '../lib/progress';
import { clearSession, loadSession, saveSession, sessionKey } from '../lib/session';
import type { ProgressStore, Question, Tip } from '../types';

export function QuizPage() {
  const [params] = useSearchParams();
  const mode = params.get('mode') || 'practice';
  const packId = params.get('pack') || '';
  const source = params.get('source') || '';
  const navigate = useNavigate();
  const [questions, setQuestions] = useState<Question[]>([]);
  const [tips, setTips] = useState<Tip[]>([]);
  const [progress, setProgress] = useState<ProgressStore>(loadProgress());
  const [ready, setReady] = useState(false);
  const [initialIndex, setInitialIndex] = useState(0);

  const key = sessionKey(mode, packId || source || 'default');

  useEffect(() => {
    Promise.all([getQuestions(), getTips(), getSprintPacks()]).then(([qs, ts, packs]) => {
      setTips(ts);
      const byId = new Map(qs.map((q) => [q.id, q]));
      const existing = loadSession(key);

      let ids: string[] = [];
      if (mode === 'wrong') {
        ids = loadProgress().wrongIds;
      } else if (mode === 'sprint') {
        if (existing?.questionIds?.length && existing.packId === packId) {
          ids = existing.questionIds;
        } else {
          const pack = packs.find((p) => p.id === packId);
          const packIds = pack?.questionIds || [];
          const fromStorage: string[] = JSON.parse(sessionStorage.getItem('xingce-sprint') || '[]');
          // sessionStorage is shared across packs — only reuse when it matches this pack
          if (
            fromStorage.length &&
            packIds.length &&
            fromStorage.length === packIds.length &&
            fromStorage.every((id, idx) => id === packIds[idx])
          ) {
            ids = fromStorage;
          } else {
            ids = packIds;
            if (packIds.length) {
              sessionStorage.setItem('xingce-sprint', JSON.stringify(packIds));
            }
          }
        }
      } else if (existing?.questionIds?.length && existing.mode === 'practice') {
        ids = existing.questionIds;
      } else {
        ids = JSON.parse(sessionStorage.getItem('xingce-session') || '[]');
      }

      const list = ids.map((id) => byId.get(id)).filter(Boolean) as Question[];
      setQuestions(list);

      if (existing && existing.questionIds.join() === ids.join()) {
        setInitialIndex(Math.min(existing.index, Math.max(list.length - 1, 0)));
      } else if (list.length) {
        saveSession({
          key,
          mode,
          packId: packId || undefined,
          questionIds: ids,
          index: 0,
          updatedAt: new Date().toISOString(),
        });
        setInitialIndex(0);
      }
      setReady(true);
    });
  }, [mode, packId, source, key]);

  const title = useMemo(() => {
    if (mode === 'wrong') return '错题重练';
    if (mode === 'sprint') return '冲刺刷题';
    if (source === 'pdd') return '拼多多26年真题';
    return '模块练习';
  }, [mode, source]);

  const backTo =
    mode === 'sprint'
      ? packId
        ? `/sprint/${packId}`
        : '/sprint'
      : mode === 'wrong'
        ? '/wrong'
        : source
          ? `/practice?source=${encodeURIComponent(source)}`
          : '/practice';

  if (!ready) return <div className="page">加载中…</div>;

  return (
    <div className="page">
      <QuizPlayer
        key={key + ':' + questions.map((q) => q.id).join(',')}
        questions={questions}
        tips={tips}
        progress={progress}
        onProgress={setProgress}
        title={title}
        backTo={backTo}
        sessionMeta={{ key, mode, packId: packId || source || undefined }}
        initialIndex={initialIndex}
        onFinished={() => {
          clearSession(key);
          if (mode === 'sprint' && packId) {
            setProgress(markSprintCleared(loadProgress(), packId));
            navigate(`/sprint/${packId}?done=1`);
          } else {
            navigate(backTo);
          }
        }}
      />
      {!questions.length ? (
        <p className="panel">
          没有可练习的题目。
          <Link to="/">回首页</Link>
        </p>
      ) : null}
    </div>
  );
}
