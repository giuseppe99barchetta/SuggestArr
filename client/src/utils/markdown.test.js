import assert from 'node:assert/strict';
import { test } from 'node:test';

import { releaseNotesToHtml } from './markdown.js';

test('bullets separated by a blank line stay in one list', () => {
  const html = releaseNotesToHtml('## Fixes\n- one\n- two\n\n* three');
  assert.equal(html, '<h3>Fixes</h3><ul><li>one</li><li>two</li><li>three</li></ul>');
});

test('markup in the notes is escaped, not rendered', () => {
  assert.equal(releaseNotesToHtml('<img src=x onerror=alert(1)>'), '<p>&lt;img src=x onerror=alert(1)&gt;</p>');
});

test('only http(s) links become anchors', () => {
  assert.match(releaseNotesToHtml('[PR](https://github.com/x/y/pull/1)'), /<a href="https:\/\/github.com\/x\/y\/pull\/1"/);
  assert.equal(releaseNotesToHtml('[x](javascript:alert(1))').includes('<a'), false);
});

test('bold and italic inside list items', () => {
  assert.equal(releaseNotesToHtml('- **new** and *nice*'), '<ul><li><strong>new</strong> and <em>nice</em></li></ul>');
});

test('horizontal rules and paragraphs', () => {
  assert.equal(releaseNotesToHtml('Intro line\nsecond\n\n---\n\nOutro'), '<p>Intro line<br>second</p><hr><p>Outro</p>');
});

test('code spans are rendered and their content left alone', () => {
  assert.equal(releaseNotesToHtml('Send `Authorization: **x**` header'), '<p>Send <code>Authorization: **x**</code> header</p>');
});

test('issue references and mentions link to GitHub', () => {
  const html = releaseNotesToHtml('Addresses #505, thanks @octo-cat.');
  assert.match(html, /<a href="https:\/\/github.com\/giuseppe99barchetta\/SuggestArr\/issues\/505"[^>]*>#505<\/a>/);
  assert.match(html, /<a href="https:\/\/github.com\/octo-cat"[^>]*>@octo-cat<\/a>/);
});

test('bare pull request URLs are shortened to their number', () => {
  const html = releaseNotesToHtml('See https://github.com/x/y/pull/42.');
  assert.match(html, /<a href="https:\/\/github.com\/x\/y\/pull\/42"[^>]*>#42<\/a>\.<\/p>$/);
});

test('indented items become a nested list', () => {
  assert.equal(releaseNotesToHtml('- a\n  - b\n- c'), '<ul><li>a<ul><li>b</li></ul></li><li>c</li></ul>');
});

test('fenced code is kept verbatim', () => {
  assert.equal(releaseNotesToHtml('```\n# not a heading\n```'), '<pre><code># not a heading</code></pre>');
});
