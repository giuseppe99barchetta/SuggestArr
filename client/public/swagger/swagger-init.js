(() => {
  "use strict";

  const configElement = document.getElementById("swagger-config");
  const loadingElement = document.getElementById("swagger-loading");

  const showError = () => {
    if (!loadingElement) return;
    loadingElement.textContent = "Unable to load the API documentation.";
    loadingElement.classList.add("api-loading--error");
  };

  if (!configElement || typeof SwaggerUIBundle === "undefined" || typeof SwaggerUIStandalonePreset === "undefined") {
    console.error("Swagger UI configuration or assets were not loaded correctly.");
    showError();
    return;
  }

  try {
    const swaggerConfig = JSON.parse(configElement.textContent);
    Object.assign(swaggerConfig, {
      validatorUrl: null,
      presets: [SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset],
      plugins: [SwaggerUIBundle.plugins.DownloadUrl],
      onComplete() {
        loadingElement?.remove();
      },
    });
    SwaggerUIBundle(swaggerConfig);
  } catch (error) {
    console.error("Unable to initialize Swagger UI:", error);
    showError();
  }
})();
