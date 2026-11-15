import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import App from './App';
import { verify } from './api';

const candidate = 'PyPI reports requests version 2.34.2.';
const info = { evidence_mode: 'fixture', receipt_protocol: '004g.receipt.v2', policies: [], live_qualification: 'Separate reviewed narrow live qualification.', scenarios: [
  { id:'supported',label:'Supported claims',candidate,description:'fixture',expected_status:200 },
  { id:'contradicted',label:'Older Python',candidate:'Older fixture text.',description:'fixture',expected_status:403 },
  { id:'unsupported',label:'Extra assertion',candidate:'Extra fixture text.',description:'fixture',expected_status:503 },
  { id:'missing-plugin',label:'Missing plugin',candidate,description:'fixture',expected_status:503 },
  { id:'provider-error',label:'Provider failure',candidate,description:'fixture',expected_status:400 },
] };
function response(status: number, value: object) { return { ok:status>=200&&status<300,status,json:async()=>value } as Response; }
function result(status = 200, outcome = 'ALLOW', text: string | null = candidate) { return { status,upstream_status:status,outcome,boundary:status===400?'provider':'policy',content:text,error:status===200?null:'Safe refusal.',exact_content_match:status===200,evidence_mode:'fixture' }; }
function setup(reply: (init?: RequestInit) => Promise<Response>) {
  const requests = vi.fn((url: RequestInfo | URL, init?: RequestInit) => {
    if (url === '/api/demo/info') return Promise.resolve(response(200, info));
    if (url === '/api/demo/verify') return reply(init);
    throw new Error('unexpected request');
  });
  vi.stubGlobal('fetch', requests);
  render(<App/>);
  return requests;
}

it('selects presets, sends custom content unchanged and clears a prior release on edit', async () => {
  const requests = setup(async init => response(200,result(200,'ALLOW',JSON.parse(String(init?.body)).candidate)));
  const editor = await screen.findByRole('textbox', { name:'Candidate response' }) as HTMLTextAreaElement;
  await waitFor(()=>expect(editor.value).toBe(candidate));
  fireEvent.click(screen.getByRole('button',{name:/Older Python/}));
  expect(editor.value).toBe('Older fixture text.');
  fireEvent.click(screen.getByRole('button',{name:/Supported claims/}));
  const text = '\t'+candidate+'\n';
  fireEvent.change(editor,{target:{value:text}});
  fireEvent.click(screen.getByRole('button',{name:'Run verification'}));
  await screen.findByText('Approved content released');
  expect(screen.getByTestId('released-content').textContent).toBe(text);
  const sent = JSON.parse(String(requests.mock.calls.find(([url])=>url==='/api/demo/verify')?.[1]?.body));
  expect(sent).toEqual({scenario:'custom',candidate:text});
  fireEvent.change(editor,{target:{value:candidate+' Extra.'}});
  expect(screen.queryByTestId('released-content')).toBeNull();
});

it.each([[403,'REJECT'],[503,'UNAVAILABLE'],[503,'INGRESS_REFUSED'],[400,'PROVIDER_ERROR']])('renders a %s %s refusal without presenting the input as released', async (status,outcome) => {
  setup(async()=>response(Number(status),result(Number(status),String(outcome),null)));
  const editor = await screen.findByRole('textbox',{name:'Candidate response'}) as HTMLTextAreaElement;
  await waitFor(()=>expect(editor.value).toBe(candidate));
  fireEvent.click(screen.getByRole('button',{name:'Run verification'}));
  await screen.findByText('NO CANDIDATE CONTENT RELEASED');
  expect(screen.queryByTestId('released-content')).toBeNull();
  expect(editor.value).toBe(candidate);
  expect(document.querySelector('.response-content')?.textContent).not.toContain(candidate);
});

it('holds loading state and exposes no answer before completion', async () => {
  let finish: (r: Response) => void = ()=>{};
  setup(()=>new Promise(resolve=>{finish=resolve;}));
  const editor = await screen.findByRole('textbox',{name:'Candidate response'}) as HTMLTextAreaElement;
  await waitFor(()=>expect(editor.value).toBe(candidate));
  fireEvent.keyDown(editor,{key:'Enter',ctrlKey:true});
  await screen.findByText('Holding the candidate');
  expect(editor.disabled).toBe(true);
  expect(screen.queryByTestId('released-content')).toBeNull();
  finish(response(200,result()));
  await screen.findByText('Approved content released');
});

it('displays a generic safe infrastructure failure instead of raw network errors', async () => {
  setup(async()=>{throw new Error('PRIVATE_NETWORK_DIAGNOSTIC');});
  const editor = await screen.findByRole('textbox',{name:'Candidate response'}) as HTMLTextAreaElement;
  await waitFor(()=>expect(editor.value).toBe(candidate));
  fireEvent.click(screen.getByRole('button',{name:'Run verification'}));
  await screen.findByRole('alert');
  expect(document.body.textContent).not.toContain('PRIVATE_NETWORK_DIAGNOSTIC');
  expect(screen.queryByTestId('released-content')).toBeNull();
});

it('rejects mismatched content and outcome records without rendering them', async () => {
  vi.stubGlobal('fetch',vi.fn(async()=>response(200,result(200,'ALLOW','PRIVATE_SUBSTITUTED_CONTENT'))));
  await expect(verify('custom',candidate,new AbortController().signal)).rejects.toThrow();
});
