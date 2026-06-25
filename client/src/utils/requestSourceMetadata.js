const METHOD_METADATA = {
  ai_search: {
    label: 'AI Search',
    shortLabel: 'AI',
    icon: 'fas fa-magic',
  },
  discover: {
    label: 'Discover',
    shortLabel: 'Discover',
    icon: 'fas fa-search',
  },
  trakt_recommendations: {
    label: 'Trakt Recommendations',
    shortLabel: 'Trakt',
    icon: 'icon-trakt',
  },
};

const SYNTHETIC_SOURCE_IDS = new Set(Object.keys(METHOD_METADATA));

function getSourceId(item) {
  return String(item?.source_id ?? item?.id ?? '');
}

export function getRequestMethodMetadata(item, options = {}) {
  if (options.sourceMode === 'ai' || item?._isAiRequest) {
    return METHOD_METADATA.ai_search;
  }

  return METHOD_METADATA[getSourceId(item)] || null;
}

export function getRequestSourceContentMetadata(item) {
  const sourceId = getSourceId(item);

  if (!item?.source_title || SYNTHETIC_SOURCE_IDS.has(sourceId)) {
    return null;
  }

  return {
    label: item.source_title,
    kind: sourceId && /^\d+$/.test(sourceId) ? 'TMDB Source' : 'Source Content',
    icon: 'fas fa-database',
  };
}
