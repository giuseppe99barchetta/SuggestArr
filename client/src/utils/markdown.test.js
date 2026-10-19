import assert from 'node:assert/strict';
import { test } from 'node:test';

import { releaseNotesToHtml } from './markdown.js';

test('consecutive bullets become one list, wherever they appear', () => {
  const html = releaseNotesToHtml('## Fixes\n- one\n- two\n\n* three');
  assert.equal(html, '<h3>Fixes</h3><ul><li>one</li><li>two</li></ul><br><ul><li>three</li></ul>');
});

test('markup in the notes is escaped, not rendered', () => {
  assert.equal(releaseNotesToHtml('<img src=x onerror=alert(1)>'), '&lt;img src=x onerror=alert(1)&gt;');
});

test('only http(s) links become anchors', () => {
  assert.match(releaseNotesToHtml('[PR](https://github.com/x/y/pull/1)'), /<a href="https:\/\/github.com\/x\/y\/pull\/1"/);
  assert.equal(releaseNotesToHtml('[x](javascript:alert(1))').includes('<a'), false);
});

test('bold and italic inside list items', () => {
  assert.equal(releaseNotesToHtml('- **new** and *nice*'), '<ul><li><strong>new</strong> and <em>nice</em></li></ul>');
});
