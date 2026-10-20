# Toad Sage with only a phone

The dashboard can collect, inspect and organize text/source feeds without a computer, an AI model or an account. It does not generate projects, execute submitted source or connect to a computer. Docker/Ollama and autonomous missions remain local-engine features.

## An unfinished paste

1. Open [Toad Sage](https://jimedusot-beep.github.io/Toadsagemode/) in ordinary Safari.
2. Paste or type material. Optional name/description/source fields are kept with the draft.
3. Wait for **Draft saved in this tab**. A draft is separate from the inbox: it has not become an ability.
4. Reload the same tab. The editor restores that draft without adding an inbox item.
5. Press **Feed Toad** to save and inspect it. A successful feed clears its draft; a failed feed retains the editor. Edits typed while a save is in progress remain a newer draft.

Drafts use this tab's session storage. Reload recovery is not a promise of recovery after closing the tab, clearing Safari data, private browsing or a device crash before the draft is stored. Keep permanent material in the inbox and export backups. If draft storage is denied/full or the input is too large, the app shows that it could not update the draft; the current editor remains available. Library saving may still work when draft storage does not.

## Save a draft in Files

**Download draft** exports unsent text and its optional fields as `toad-feed-draft.json`. To recover it later, open **Add a name, description, source, or files**, then choose the file under **Restore a downloaded draft**. Restoration fills the editor; it does not feed, verify or install anything. Invalid/future draft formats are refused without replacing the current editor. Imports allow up to 2 MB of encoded JSON while keeping pasted text at 250,000 UTF-8 bytes and bounded optional fields; escaping can make a valid draft file larger than its text. Oversized editor contents download as an explicitly labeled manual recovery file, preserving the material without claiming it can be automatically restored.

If replacing unsent material, download that material first. Confirmation is required before replacing an existing draft. A library backup and a draft download are different files; use their respective import controls.

Attachment contents are **not** kept in a draft/download. After restoring a draft that had files selected, the app asks you to select them again. It blocks Feed Toad until you do so or explicitly choose **Continue without attachments**. This prevents accidentally saving the notes while forgetting the source files.

Unreadable saved drafts are left untouched and can be downloaded raw. **Clear input** explicitly clears the editor and this tab's draft. A normal successful feed does not discard an unreadable older draft. Raw recovery files may need manual repair; they are not automatically treated as valid feeds or backups.

## More than one tab

Updated tabs listen for inbox changes and coordinate writes with Web Locks when the browser offers that API. Each write also checks that its original stored snapshot is still current. An observed conflict updates the inbox and asks you to review/retry while keeping the Feed Toad editor intact. Export also checks for newer inbox data before preparing a backup.

An open name/description editor with unsaved changes is preserved instead of being automatically rebuilt by another tab. If there is a conflict, copy those edits and reload before trying again; the app does not silently merge metadata. Async imports merge against the current library after reading the file, so an intervening save is retained.

Web Locks coordinate cooperating tabs running this version. Old tabs and browsers without Web Locks cannot provide an atomic multi-tab transaction; the stale-snapshot check alone cannot eliminate every simultaneous-write race. Reload old tabs after updating. If the app advises using one tab, do so. Keep backups regardless.

## Privacy and checks

Drafts and inbox entries stay in browser storage. Downloads go to the location Safari offers; the app cannot confirm that you kept the file. Neither draft persistence nor import/export uploads source to GitHub. Imported HTML and code remain text.

Development checks use actual desktop WebKit with an iPhone viewport. They cover reload and metadata recovery, attachments, draft download/import, denied/corrupt draft storage, stale writes with/without locks, queued writes, pending metadata, in-flight backup imports, and newer draft edits during source uploads, alongside the existing inbox checks. These checks do not replace a physical iPhone Safari retest.

References: [session storage lifecycle](https://developer.mozilla.org/en-US/docs/Web/API/Window/sessionStorage), [Web Locks coordination specification](https://w3c.github.io/web-locks/).
