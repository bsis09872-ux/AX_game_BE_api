import { createPlayPage } from './play.js';

// 첫 프레임을 화면 밖에서 준비한 후 공통 page-renderer가 본문을 교체한다.
export async function preparePlayPage({ root, signal, ...context }) {
    const host = document.createElement('div');
    host.dataset.pagePreparation = '';
    host.setAttribute('aria-hidden', 'true');
    host.inert = true;
    Object.assign(host.style, {
        position: 'fixed', left: '-100000px', top: '0',
        visibility: 'hidden', width: '96%',
    });
    host.append(...root.cloneNode(true).childNodes);
    document.body.append(host);
    signal.addEventListener('abort', () => host.remove(), { once: true });

    try {
        const runtime = await createPlayPage({ ...context, root: host, signal });
        return {
            attach() {
                root.replaceChildren(...host.childNodes);
                host.remove();
            },
            activate: runtime.activate,
        };
    } catch (error) {
        host.remove();
        throw error;
    }
}

export function initPlayPage(context) {
    const scope = new AbortController();
    context.signal.addEventListener('abort', () => scope.abort(), { once: true });
    createPlayPage({ ...context, signal: scope.signal, url: new URL(location.href) })
        .then((runtime) => runtime.activate())
        .catch((error) => {
            scope.abort();
            if (!context.signal.aborted) {
                context.root.querySelector('#prompt').textContent = error.message;
            }
        });
}
