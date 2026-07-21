<template><div ref="host"></div></template>

<script>
import axios from 'axios';
import SwaggerUIBundle from 'swagger-ui-dist/swagger-ui-bundle.js';
import 'swagger-ui-dist/swagger-ui.css';

export default {
  name: 'ApiDocsPage',
  mounted() {
    const shadowRoot = this.$refs.host.attachShadow({ mode: 'open' });
    const target = document.createElement('div');
    const swaggerSheet = Array.from(document.styleSheets).find((sheet) => {
      try { return Array.from(sheet.cssRules).some(rule => rule.cssText.includes('.swagger-ui')); } catch { return false; }
    });
    if (swaggerSheet) {
      const style = document.createElement('style');
      style.textContent = Array.from(swaggerSheet.cssRules).map(rule => rule.cssText).join('\n');
      shadowRoot.appendChild(style);
    }
    shadowRoot.appendChild(target);
    SwaggerUIBundle({
      url: axios.getUri({ url: '/api/v1/openapi.json' }),
      dom_node: target,
      deepLinking: true,
      displayRequestDuration: true,
      persistAuthorization: false,
      tryItOutEnabled: true,
    });
  },
};
</script>
