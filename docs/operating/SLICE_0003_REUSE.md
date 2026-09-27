# Flow/Veo preflight reuse record

Source: blackshark03z/AutoVideoPipeline

Revision: `826e01866af1b28ed29b6fbb51cabb71f31ef561`

Files inspected:
- `videopipeline/stages/stage2_assets/flow_generator.py`
- `videopipeline/doctor.py`
- `tests/test_flow_session_binding.py`

## REUSED

- Essential-cookie expiry check vocabulary: SID, HSID, __Secure-1PSID, __Secure-1PSIDTS.
- Persistent `google-flow-session-v1` project binding format.
- Read-only browser navigation preflight and cookie sameSite normalization.

## ADAPTED

- Local validity is separate from live project readiness.
- Exact project URL comparison replaces substring matching; matching URL also requires a prompt surface.
- Exceptions and health output expose fixed diagnostic codes only, with no cookie values, local paths, project IDs or transport URLs.
- READY alone is routable; other states fail closed.

## NOT REUSED

- Generation, project creation/discovery, credential activation/login, polling and downloads.
- Broad UI/settings selectors and model/tier assumptions.
- Existing stage architecture and fallback readiness based only on a Flow hostname.

## Capability evidence

The inspected generator implements text prompt submission in video mode, establishing a current transport text-to-video mechanism. This enables only `supports_text_to_video`. All other flags remain false because usable support has not been established in this new adapter. Generation is disabled regardless of this capability.

## Optional authenticated preflight

NOT_RUN: no FLOW_COOKIE_PATH, FLOW_SESSION_PATH or FLOW_PROJECT_ID is configured in this execution environment. No credentials were searched for, acquired or refreshed. Authenticated provider qualification remains unverified.
