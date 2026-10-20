# Review fixes — 20 October 2026

Reviewed against main `ba3a00b`, preserving the new private bridge, agent, Git drafts and quarantined skill catalog.

Confirmed defects and changes:

- Large browser backups could fail restoration because imports copied already-retained source into provenance metadata. Imports now retain differing claims and unknown metadata without duplicating identical source. Library-level custom metadata is also preserved. Backups use compact JSON so formatting cannot push an otherwise valid export beyond the import byte limit.
- Search, filtering and other same-tab renders discarded unsaved candidate names/descriptions. Pending edits now survive renders and hidden filters, with explicit discard. Successful saves clear only the submitted edits; newer edits typed while a save waits remain pending. Pending edits continue to block cross-tab replacement.
- Editing metadata on an imported structured package incorrectly applied the smaller paste limit to its original JSON. Metadata editing now validates the existing manifest without reparsing source.
- Bounded agent edits replaced complete file records with Git snapshots, discarding file metadata and falsely rejecting unchanged tests. Edits now update content in copied original file records.

Regression coverage includes large download/restore, custom metadata and untrusted claims, large structured package edits, pending edits across search and feeding, an in-flight metadata save, and agent source/test metadata preservation. No imported code is executed by these regressions. Physical iPhone behavior and live private-host Docker/Ollama execution remain unverified here.
