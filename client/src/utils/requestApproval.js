// Mirrors requires_request_approval() in api_service/services/seer/seer_client.py,
// so every page agrees on whether suggestions wait for a review.

function asBool(value) {
  if (typeof value === 'string') return ['true', '1', 'yes', 'on'].includes(value.trim().toLowerCase());
  return Boolean(value);
}

/**
 * Whether a job's suggestions wait for approval: `manual` always does, `automatic`
 * never does, and `inherit` (or no mode) follows the global REQUIRE_REQUEST_APPROVAL.
 */
export function jobRequiresApproval(job, globalDefault) {
  const mode = job?.delivery_mode || 'inherit';
  if (mode === 'manual') return true;
  if (mode === 'automatic') return false;
  return asBool(globalDefault);
}

/**
 * Whether any job sends suggestions to the approval queue, from a GET /api/jobs response body.
 */
export function approvalEnabled(jobsResponse) {
  const globalDefault = jobsResponse?.request_approval_default;
  return (jobsResponse?.jobs || []).some(job => jobRequiresApproval(job, globalDefault));
}
