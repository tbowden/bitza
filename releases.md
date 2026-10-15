# Releases

## v0.2.0
This release is prior to implementing file handling on the frontend. 

### Where things stand

Stage 7 backend is done: five endpoints, content sniffing for documents and images, 332 tests. The frontend has no document model, service or component. The work is:

BitzaDocument model and DocumentService.
A documents section next to <app-image-gallery> on the detail card.
A metadata dialog.

I checked the model against the schema file, as the field-drift lesson says. The fields are id, bitza_id, doc_type, title, source_url, note, original_filename, content_type, size_bytes, sha256, uploaded_by, uploaded_by_display_name, uploaded_at. doc_type is datasheet | sds | manual | other. The list endpoint returns the same shape as upload and PATCH, so there is no list/detail split to trip over this time.

Things I found that affect the decisions
Dev can’t read Content-Disposition. In dev the app (4200) is cross-origin to the API (8000), and CORSMiddleware sets no expose_headers. So the save-as filename must come from original_filename in the list metadata, which is also what the backend uses. Production is same-origin, so this would only bite in dev.
Blob request errors arrive as a Blob, not JSON. This matters for download, where a 404 “Document file not found” is an expected state by design, since DB/filesystem sync is a separate admin process.
413 as well as 415. The open-issues doc only mentions 415. A reverse proxy’s 413 would be HTML, not {detail}, and a 422’s detail is an array.
ImageGallery hides list-load failures. Its catchError(() => of([])) shows “No images yet.” when the load actually failed. Copying that verbatim would do the same for documents.
Template convention conflict. The guidelines you pasted say to prefer inline templates for small components. The repo’s .claude/CLAUDE.md says external templates. I’ll follow the repo (external .html/.scss) unless you say otherwise.

Assumptions I’d make without asking: the section shows for all bitza kinds (the backend allows it), delete reuses ConfirmDialog, and ImageGallery stays untouched in this patch.

Decisions

1. Upload flow

(a) Pick file, upload immediately, edit metadata afterwards (what images do). Fastest for bulk entry, but metadata always costs a second step, and errors can only go in a snackbar.
(b) Pick file, then a dialog with the metadata form, upload on Save. One extra click per file. source_url is easiest to capture at this moment. A 415/413 can show inside the dialog with the file and typed metadata kept. The same dialog serves create and edit, with a file row in create mode only.
(c) Dialog opens first with the picker inside. Same benefits as (b), but the picker has to live in the dialog.
Lean: (b). Save works with every field blank, so it’s only one extra click.

2. File picker control

(a) Material button plus a hidden file input, triggered via click() on a template reference. hidden takes the input out of the tab order and accessibility tree, so the button is the only control.
(b) Keep ImageGallery’s label pattern. Your open-issues doc suspects the role="button" span inside a label fails axe.
(c) A visible native <input type=file>. The most accessible by default and shows the chosen filename, but it’s unstyled.
Lean: (a), with the chosen filename shown as text. I’d leave accept off, because the backend sniffs content and a client extension list is a second allow-list to keep in sync.

3. Download

(a) HttpClient blob plus a temporary <a download>. This is the approach in your docs. The 50 MB default cap makes holding it in memory fine. Revoke the object URL afterwards.
(b) A short-lived download token from the backend. The browser handles the download natively, so you get streaming and progress with no memory cost. But it needs a backend change and a new auth surface.
(c) Open the blob in a tab. Rejected, for the origin and nosniff reasons in your docs.
Lean: (a), with a small saveBlob(blob, filename) helper in shared/ so images could reuse it later. Show a per-row disabled state rather than a progress bar. Map 404 to “file missing on the server” instead of parsing the Blob error.

4. List loading and refetch

(a) Copy ImageGallery’s reload signal pattern as-is. Consistent, but it inherits the swallowed-error problem.
(b) The same pattern with an explicit error state (“Couldn’t load documents” with a retry), distinct from “No documents yet.”
(c) httpResource. It’s signal-native and would remove the toObservable/toSignal plumbing, but nothing else in the app uses it. I’m not sure of its stability in v22 and would check the compiled source before relying on it.
Lean: (b).

5. Row layout and actions

(a) A list with inline download, edit and delete icon buttons, each with a contextual label such as “Download LM358 datasheet”. There are three tab stops per row, but everything is visible, and a handful of documents per bitza is the expected case.
(b) An overflow mat-menu. Fewer tab stops, but an extra click and more focus handling to get right.
(c) mat-table. Heavy for a narrow detail card.
Lean: (a). The display label falls back from title to original_filename, then “Untitled document”. source_url would render as a link showing the hostname, with target="_blank" rel="noopener noreferrer", and the accessible name should say it opens a new tab.

6. Form validation and PATCH shape

Validation: either (a) a client-side http(s) check plus the backend as backstop, or (b) rely on the backend’s 422 and show it in a banner. I lean (a). I’d verify how pattern() treats empty strings in Signal Forms from the compiled source first, as your frontend doc advises.
PATCH: send all four fields every time. A blank gets normalised to None, which clears it, so there’s no null-versus-omitted logic client-side. The cost is last-write-wins on four optional text fields, which I think is acceptable. The alternative is sending only changed fields.

7. Error messages

(a) Per-component handling.
(b) One shared apiErrorMessage(err, fallback) helper that handles string detail, array detail, non-JSON bodies and status 0.
Lean: (b). Retrofitting ImageGallery to use it, so it stops saying “Upload failed.”, would be a separate small patch.

8. Testing and accessibility verification

Tests: add a document.service.spec.ts in the existing HttpTestingController style. I’d keep the first-ever component spec out of this patch. It needs a new setup for MatDialog, and jsdom lacks URL.createObjectURL.
Accessibility:
(a) The axe DevTools extension before and after. No setup, real browser, covers contrast.
(b) axe-core inside Vitest/jsdom. It can’t check contrast or layout, so it would give false comfort.
(c) @axe-core/playwright. Repeatable, but adds Playwright and e2e infrastructure.
Lean: (a) now, (c) as a separate backlog item. I can’t run a browser here, so the baseline has to come from you, and the patch would be labelled unverified for axe.

Tell me where you disagree with the leans and I’ll scope the patch to match.
