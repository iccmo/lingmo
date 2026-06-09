# API Reference

Generated from `novel_writer.server:app` with `python3 scripts/export_api_docs.py`.

Total endpoints: 202

## agent-diagnostics

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/novels/{novel_id}/abandonment-candidates` | Abandonment Candidates |
| `POST` | `/api/novels/{novel_id}/anti-narrative` | Get Anti Narrative |
| `GET` | `/api/novels/{novel_id}/attention-curve` | Attention Curve |
| `GET` | `/api/novels/{novel_id}/boundary-check` | Boundary Check |
| `POST` | `/api/novels/{novel_id}/draft-protect` | Draft Protect |
| `GET` | `/api/novels/{novel_id}/ending-candidates` | Ending Candidates |
| `GET` | `/api/novels/{novel_id}/energy-form` | Get Energy Form |
| `GET` | `/api/novels/{novel_id}/expectation-check` | Expectation Check |
| `GET` | `/api/novels/{novel_id}/info-gradient` | Get Info Gradient |
| `GET` | `/api/novels/{novel_id}/midpoint-health` | Midpoint Health |
| `GET` | `/api/novels/{novel_id}/narrative-distance` | Get Narrative Distance |
| `GET` | `/api/novels/{novel_id}/narrative-voice` | Get Narrative Voice |
| `GET` | `/api/novels/{novel_id}/neg-space-health` | Neg Space Health |
| `GET` | `/api/novels/{novel_id}/pov-shifts` | Get Pov Shifts |
| `GET` | `/api/novels/{novel_id}/pre-understanding` | Pre Understanding |
| `GET` | `/api/novels/{novel_id}/psych-time` | Psych Time |
| `GET` | `/api/novels/{novel_id}/reader-state` | Get Reader State |
| `GET` | `/api/novels/{novel_id}/reverse-reading` | Reverse Reading |
| `GET` | `/api/novels/{novel_id}/rituals` | Rituals |
| `GET` | `/api/novels/{novel_id}/scream-moments` | Scream Moments |
| `GET` | `/api/novels/{novel_id}/self-check` | System Self Check |
| `GET` | `/api/novels/{novel_id}/time-spiral` | Time Spiral |
| `GET` | `/api/novels/{novel_id}/wound-arc` | Get Wound Arc |
| `POST` | `/api/text/negative-space` | Negative Space |
| `POST` | `/api/text/touch-analysis` | Touch Analysis |

## agent-pipeline

| Method | Path | Summary |
|---|---|---|
| `POST` | `/api/novels/{novel_id}/agent-pipeline` | Run Agent Pipeline |
| `GET` | `/api/novels/{novel_id}/agent-report` | Agent Report |

## analytics

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/analytics-dashboard` | Analytics Dashboard |
| `GET` | `/api/costs` | Get Costs |
| `GET` | `/api/costs/summary` | Costs Summary |
| `GET` | `/api/daily` | Daily Digest |
| `GET` | `/api/insights` | Cross Novel Insights |
| `GET` | `/api/novels/{novel_id}/acquisition-review` | Acquisition Review |
| `GET` | `/api/novels/{novel_id}/analytics` | Get Analytics |
| `GET` | `/api/novels/{novel_id}/ask` | Ask Novel |
| `GET` | `/api/novels/{novel_id}/cockpit` | Writers Cockpit |
| `POST` | `/api/novels/{novel_id}/compare` | Compare Chapters |
| `GET` | `/api/novels/{novel_id}/continuity` | Chapter Continuity |
| `GET` | `/api/novels/{novel_id}/diffs` | Chapter Diffs |
| `GET` | `/api/novels/{novel_id}/estimate` | Estimate Cost |
| `POST` | `/api/novels/{novel_id}/generate-cover` | Generate Cover |
| `GET` | `/api/novels/{novel_id}/monetization-status` | Monetization Status |
| `GET` | `/api/novels/{novel_id}/optimal-publish-time` | Optimal Publish Time |
| `POST` | `/api/novels/{novel_id}/optimize-prompt` | Optimize Prompt |
| `GET` | `/api/novels/{novel_id}/packaging` | Generate Packaging |
| `GET` | `/api/novels/{novel_id}/reading-stats` | Reading Stats |
| `GET` | `/api/novels/{novel_id}/resume` | Resume Generation |
| `GET` | `/api/novels/{novel_id}/retention-score` | Retention Score |
| `GET` | `/api/novels/{novel_id}/timeline` | Book Timeline |
| `GET` | `/api/publishing-dashboard` | Publishing Dashboard |

## audiobook

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/audio/data` | Audio Load |
| `POST` | `/api/audio/sync` | Audio Sync |
| `GET` | `/api/novels/{novel_id}/chapters/{chapter_num}/tts` | Chapter Tts |
| `GET` | `/api/novels/{novel_id}/chapters/{chapter_num}/tts-dramatic` | Chapter Tts Dramatic |
| `GET` | `/api/novels/{novel_id}/voice-profile` | Get Voice Profile |
| `GET` | `/api/search` | Search Chapters |
| `GET` | `/api/writer-voices` | List Writer Voices |

## backup

| Method | Path | Summary |
|---|---|---|
| `POST` | `/api/backup/cloud` | Cloud Backup |
| `GET` | `/api/backup/status` | Backup Status |

## chapters

| Method | Path | Summary |
|---|---|---|
| `POST` | `/api/novels/{novel_id}/chapters/reorder` | Reorder Chapters |
| `DELETE` | `/api/novels/{novel_id}/chapters/{chapter_num}` | Delete Chapter |
| `GET` | `/api/novels/{novel_id}/chapters/{chapter_num}` | Get Chapter |
| `PUT` | `/api/novels/{novel_id}/chapters/{chapter_num}` | Save Chapter |
| `POST` | `/api/novels/{novel_id}/chapters/{chapter_num}/fix-formatting` | Fix Chapter Formatting |
| `GET` | `/api/novels/{novel_id}/chapters/{chapter_num}/versions` | Chapter Versions |
| `GET` | `/api/novels/{novel_id}/chapters/{chapter_num}/versions/{version_id}` | Chapter Version Content |

## constraints

| Method | Path | Summary |
|---|---|---|
| `POST` | `/api/novels/{novel_id}/constraint-collapse` | Constraint Collapse |
| `GET` | `/api/novels/{novel_id}/preview-constraints` | Preview Constraints |
| `GET` | `/api/novels/{novel_id}/test-constraints` | Test Constraint Compression |
| `GET` | `/api/test-all-constraints` | Test All Constraints |

## drafts

| Method | Path | Summary |
|---|---|---|
| `POST` | `/api/novels/{novel_id}/draft` | Draft Directions |
| `POST` | `/api/novels/{novel_id}/expand` | Expand Chapter |
| `GET` | `/api/novels/{novel_id}/preview` | Preview Chapter |

## drama

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/novels/comfyui/test` | Test Comfyui Connection |
| `GET` | `/api/novels/film-settings` | Get Film Settings |
| `PUT` | `/api/novels/film-settings` | Update Film Settings |
| `POST` | `/api/novels/{novel_id}/chapters/{chapter_num}/music/generate` | Generate Music |
| `POST` | `/api/novels/{novel_id}/chapters/{chapter_num}/produce` | Produce Chapter |
| `POST` | `/api/novels/{novel_id}/chapters/{chapter_num}/voice/generate` | Generate Voice |
| `POST` | `/api/novels/{novel_id}/produce/batch` | Batch Produce |
| `POST` | `/api/novels/{novel_id}/visual-bible/character-refs/generate` | Generate Character Refs |

## exports

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/novels/{novel_id}/chapters/{chapter_num}/export` | Export Chapter |
| `GET` | `/api/novels/{novel_id}/export` | Export Novel |
| `GET` | `/api/novels/{novel_id}/export-enhanced-epub` | Export Enhanced Epub Endpoint |
| `GET` | `/api/novels/{novel_id}/export-enhanced-pdf` | Export Enhanced Pdf Endpoint |
| `GET` | `/api/novels/{novel_id}/export-epub` | Export Epub |
| `GET` | `/api/novels/{novel_id}/export-full` | Export Full Novel |
| `GET` | `/api/novels/{novel_id}/export-mobi` | Export Mobi |
| `GET` | `/api/novels/{novel_id}/export-pdf` | Export Pdf |

## foreshadowing

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/novels/{novel_id}/foreshadowing` | Get Foreshadowing Audit |
| `POST` | `/api/novels/{novel_id}/foreshadowing` | Add Foreshadowing Manual |
| `GET` | `/api/novels/{novel_id}/foreshadowing/all` | Get All Foreshadowing |
| `POST` | `/api/novels/{novel_id}/foreshadowing/{fs_id}/resolve` | Resolve Foreshadowing |

## generation

| Method | Path | Summary |
|---|---|---|
| `POST` | `/api/novels/{novel_id}/auto/once` | Auto Once |
| `POST` | `/api/novels/{novel_id}/auto/start` | Auto Start |
| `POST` | `/api/novels/{novel_id}/auto/stop` | Auto Stop |
| `POST` | `/api/novels/{novel_id}/generate` | Trigger Generate |
| `POST` | `/api/novels/{novel_id}/generate-batch` | Trigger Generate Batch |
| `GET` | `/api/novels/{novel_id}/generate/queue-status` | Generate Queue Status |
| `GET` | `/api/novels/{novel_id}/generate/stream` | Generate Stream Sse |

## imports

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/market-trends` | Market Trends |
| `POST` | `/api/novels/extract-dna` | Extract Narrative Dna |
| `POST` | `/api/novels/import` | Import Novel |
| `POST` | `/api/novels/search` | Search Novels |
| `POST` | `/api/novels/{novel_id}/clone` | Clone Novel |
| `POST` | `/api/novels/{novel_id}/import-chapters` | Import Chapters |

## novels

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/novels` | List Novels |
| `POST` | `/api/novels` | Create Novel |
| `DELETE` | `/api/novels/{novel_id}` | Delete Novel |
| `GET` | `/api/novels/{novel_id}` | Get Novel |

## orchestration

| Method | Path | Summary |
|---|---|---|
| `POST` | `/api/autonomous-novel` | Autonomous Novel |
| `POST` | `/api/demo` | Create Demo |
| `POST` | `/api/novel-farm` | Novel Farm |
| `GET` | `/api/novels/{novel_id}/check-ending` | Check Ending |
| `POST` | `/api/novels/{novel_id}/pipeline` | Trigger Pipeline |
| `POST` | `/api/novels/{novel_id}/world-bible` | Generate World Bible |

## publishing

| Method | Path | Summary |
|---|---|---|
| `POST` | `/api/novels/{novel_id}/publish` | Trigger Publish |
| `GET` | `/api/novels/{novel_id}/publish-status` | Publish Status |

## quality

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/novels/{novel_id}/algorithm-optimize` | Algorithm Optimize |
| `GET` | `/api/novels/{novel_id}/chapters/{chapter_num}/fact-check` | Fact Check Chapter |
| `POST` | `/api/novels/{novel_id}/chapters/{chapter_num}/polish-reverse` | Reverse Polish |
| `POST` | `/api/novels/{novel_id}/chapters/{chapter_num}/proofread` | Proofread Chapter |
| `GET` | `/api/novels/{novel_id}/classic-assessment` | Classic Assessment |
| `GET` | `/api/novels/{novel_id}/freshness-check` | Freshness Check |
| `GET` | `/api/novels/{novel_id}/quality-gate` | Get Quality Gate |
| `GET` | `/api/novels/{novel_id}/report` | Quality Report |
| `GET` | `/api/novels/{novel_id}/spellcheck` | Spellcheck Novel |

## revision

| Method | Path | Summary |
|---|---|---|
| `POST` | `/api/ab-test` | Ab Test Opening |
| `POST` | `/api/novels/{novel_id}/batch-generate` | Trigger Batch Generate |
| `POST` | `/api/novels/{novel_id}/chapters/{chapter_num}/humanize` | Humanize Chapter |
| `POST` | `/api/novels/{novel_id}/chapters/{chapter_num}/revise` | Revise Chapter |
| `GET` | `/api/novels/{novel_id}/consistency-score` | Get Consistency Score |
| `POST` | `/api/novels/{novel_id}/evolve` | Evolve Novel |
| `POST` | `/api/novels/{novel_id}/final-polish` | Final Polish |
| `POST` | `/api/novels/{novel_id}/generate-classic` | Trigger Generate Classic |
| `POST` | `/api/novels/{novel_id}/polish` | Polish Novel |
| `POST` | `/api/novels/{novel_id}/revise-opening` | Trigger Revise Opening |

## script

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/novels/{novel_id}/chapters/{chapter_num}/prompts` | Get Image Prompts |
| `POST` | `/api/novels/{novel_id}/chapters/{chapter_num}/prompts/generate` | Generate Image Prompts |
| `GET` | `/api/novels/{novel_id}/chapters/{chapter_num}/shots` | Get Shots With Images |
| `GET` | `/api/novels/{novel_id}/chapters/{chapter_num}/storyboard` | Get Storyboard |
| `GET` | `/api/novels/{novel_id}/chapters/{chapter_num}/storyboard/export` | Export Storyboard |
| `POST` | `/api/novels/{novel_id}/chapters/{chapter_num}/storyboard/generate` | Generate Storyboard |
| `GET` | `/api/novels/{novel_id}/visual-bible` | Get Visual Bible |
| `POST` | `/api/novels/{novel_id}/visual-bible/character-refs/upload` | Upload Character Ref |
| `GET` | `/api/novels/{novel_id}/visual-bible/export` | Export Visual Bible |
| `POST` | `/api/novels/{novel_id}/visual-bible/generate` | Generate Visual Bible |

## settings-providers

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/providers` | List Providers |
| `PUT` | `/api/providers/{provider_id}` | Update Provider |
| `POST` | `/api/providers/{provider_id}/test` | Test Provider |
| `GET` | `/api/settings` | Settings Load |
| `POST` | `/api/settings/sync` | Settings Sync |

## story-world

| Method | Path | Summary |
|---|---|---|
| `POST` | `/api/novels/{novel_id}/characters` | Add Character |
| `DELETE` | `/api/novels/{novel_id}/characters/{char_key}` | Delete Character |
| `PUT` | `/api/novels/{novel_id}/characters/{char_key}` | Update Character |
| `POST` | `/api/novels/{novel_id}/consistency/{issue_id}/fix` | Mark Consistency Fixed |
| `GET` | `/api/novels/{novel_id}/cost-ledger` | Get Cost Ledger |
| `GET` | `/api/novels/{novel_id}/counterpoint` | Get Counterpoint |
| `POST` | `/api/novels/{novel_id}/factions` | Add Faction |
| `DELETE` | `/api/novels/{novel_id}/factions/{faction_id}` | Delete Faction |
| `PUT` | `/api/novels/{novel_id}/factions/{faction_id}` | Update Faction |
| `GET` | `/api/novels/{novel_id}/outline` | Get Outline |
| `POST` | `/api/novels/{novel_id}/outline` | Save Outline |
| `DELETE` | `/api/novels/{novel_id}/outline/{chapter_num}` | Delete Outline Item |
| `POST` | `/api/novels/{novel_id}/seed-bible` | Seed Bible From Existing |
| `GET` | `/api/novels/{novel_id}/story-bible` | Get Story Bible |
| `POST` | `/api/novels/{novel_id}/suggest-outline` | Suggest Outline |
| `GET` | `/api/novels/{novel_id}/unsaid` | Get Unsaid |
| `POST` | `/api/novels/{novel_id}/unsaid` | Add Unsaid |
| `DELETE` | `/api/novels/{novel_id}/unsaid/{entry_id}` | Remove Unsaid |
| `PUT` | `/api/novels/{novel_id}/world` | Update World |
| `POST` | `/api/seed-all-bibles` | Seed All Bibles |
| `POST` | `/api/text/analyze` | Analyze Text |

## system

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/health` | Health |
| `GET` | `/api/logs` | Get Logs |
| `GET` | `/api/ping` | Ping |
| `POST` | `/api/polish-novel-idea` | Polish Novel Idea |
| `GET` | `/api/status` | System Status |
| `POST` | `/api/suggest-novel` | Suggest Novel |

## v2

| Method | Path | Summary |
|---|---|---|
| `GET` | `/api/v2/health` | Health Check |
| `GET` | `/api/v2/novels` | List Novels |
| `POST` | `/api/v2/novels` | Create Novel |
| `DELETE` | `/api/v2/novels/{novel_id}` | Delete Novel |
| `GET` | `/api/v2/novels/{novel_id}` | Get Novel |
| `PUT` | `/api/v2/novels/{novel_id}` | Update Novel |
| `DELETE` | `/api/v2/novels/{novel_id}/chapters/{chapter_num}` | Delete Chapter |
| `GET` | `/api/v2/novels/{novel_id}/chapters/{chapter_num}` | Get Chapter |
| `PUT` | `/api/v2/novels/{novel_id}/chapters/{chapter_num}` | Save Chapter |
| `GET` | `/api/v2/novels/{novel_id}/character-blueprints` | Get Character Blueprints |
| `POST` | `/api/v2/novels/{novel_id}/character-blueprints` | Save Character Blueprints |
| `DELETE` | `/api/v2/novels/{novel_id}/character-blueprints/{char_id}` | Delete Character Blueprint |
| `POST` | `/api/v2/novels/{novel_id}/generate` | Trigger Generate |
| `POST` | `/api/v2/novels/{novel_id}/generate-batch` | Trigger Generate Batch |
| `GET` | `/api/v2/novels/{novel_id}/generate/queue-status` | Queue Status |
| `GET` | `/api/v2/novels/{novel_id}/generate/status` | Gen Status |
| `GET` | `/api/v2/novels/{novel_id}/generate/stream` | Generate Stream Sse |
| `DELETE` | `/api/v2/novels/{novel_id}/soul-fingerprint` | Delete Soul |
| `GET` | `/api/v2/novels/{novel_id}/soul-fingerprint` | Get Soul |
| `POST` | `/api/v2/novels/{novel_id}/soul-fingerprint` | Save Soul |
| `GET` | `/api/v2/novels/{novel_id}/traces` | Get Traces |
| `GET` | `/api/v2/novels/{novel_id}/traces/latest` | Get Latest Trace |
| `GET` | `/api/v2/status` | System Status |
