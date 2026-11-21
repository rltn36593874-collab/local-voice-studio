# ElevenLabs REST 엔드포인트 전체 목록 (부록)

- 작성: 백엔드팀, 2026-11-21. 출처: https://elevenlabs.io/docs/openapi/api-reference-2.json (OpenAPI 3.1, info.version 1.0.0, 2026-11-21 내려받음). `openapi/api-reference.json`(172 경로)은 이 파일(377 경로)의 부분집합이라 생략.
- 명세에서 기계적으로 뽑은 표다(경로·메서드·태그·요약 원문). 본문 분석은 `04-backend-api-engine.md`.
- 에이전트(`/v1/convai/*`)·리셉션(`/v1/reception/*`)은 본 과업 범위 밖이라 개수만 적는다: convai 239개, reception 75개 오퍼레이션.

| 메서드 | 경로 | 태그 | 요약 |
|---|---|---|---|
| GET | `/v1/assets` | Assets | List Assets |
| POST | `/v1/assets` | Assets | Upload Asset |
| GET | `/v1/assets/{asset_id}` | Assets | Get Asset |
| DELETE | `/v1/assets/{asset_id}` | Assets | Delete Asset |
| GET | `/v1/audio-effects/catalog` | audioEffects | Get Audio Effects Catalog |
| POST | `/v1/audio-isolation` | audioIsolation | Audio isolation |
| GET | `/v1/audio-isolation/history` | audioIsolation | Get Audio Isolation History |
| DELETE | `/v1/audio-isolation/history/{history_item_id}` | audioIsolation | Delete Audio Isolation History Item |
| POST | `/v1/audio-isolation/stream` | audioIsolation | Audio isolation stream |
| POST | `/v1/audio-native` | audioNative | Create audio native project |
| POST | `/v1/audio-native/content` | audioNative | Update Audio-Native Content From Url |
| POST | `/v1/audio-native/{project_id}/content` | audioNative | Update audio native project |
| GET | `/v1/audio-native/{project_id}/settings` | audioNative | Get Audio Native Project Settings |
| POST | `/v1/content-provenance/watermark` | contentProvenance | Check Watermark |
| GET | `/v1/dubbing` | dubbing | List Dubs |
| POST | `/v1/dubbing` | dubbing | Dub a video or audio file |
| GET | `/v1/dubbing/project` | project | List Dubbing Projects |
| POST | `/v1/dubbing/project` | project | Create Dubbing Project |
| GET | `/v1/dubbing/project/{project_id}` | project | Get Dubbing Project |
| DELETE | `/v1/dubbing/project/{project_id}` | project | Delete Dubbing Project |
| GET | `/v1/dubbing/project/{project_id}/language` | language | List Dubbing Language Targets |
| POST | `/v1/dubbing/project/{project_id}/language` | language | Create Dubbing Language Target |
| GET | `/v1/dubbing/project/{project_id}/language/{language_id}` | language | Get Dubbing Language Target |
| DELETE | `/v1/dubbing/project/{project_id}/language/{language_id}` | language | Delete Dubbing Language Target |
| GET | `/v1/dubbing/project/{project_id}/language/{language_id}/transcript` | transcript | Get Dubbing Target Transcript |
| POST | `/v1/dubbing/project/{project_id}/language/{language_id}/transcript/regenerate` | transcript | Regenerate Dubbing Target |
| PATCH | `/v1/dubbing/project/{project_id}/language/{language_id}/transcript/segment/{segment_id}` | transcript | Update Dubbing Target Transcript Segment |
| PATCH | `/v1/dubbing/project/{project_id}/language/{language_id}/transcript/segments` | transcript | Update Dubbing Target Transcript Segments |
| GET | `/v1/dubbing/project/{project_id}/transcript` | transcript | Get Dubbing Transcript |
| POST | `/v1/dubbing/project/{project_id}/transcript/segment` | transcript | Add Dubbing Transcript Segment |
| PATCH | `/v1/dubbing/project/{project_id}/transcript/segment/{segment_id}` | transcript | Update Dubbing Transcript Segment |
| DELETE | `/v1/dubbing/project/{project_id}/transcript/segment/{segment_id}` | transcript | Delete Dubbing Transcript Segment |
| PATCH | `/v1/dubbing/project/{project_id}/transcript/segments` | transcript | Update Dubbing Transcript Segments |
| GET | `/v1/dubbing/{dubbing_id}` | dubbing | Get dubbing |
| DELETE | `/v1/dubbing/{dubbing_id}` | dubbing | Delete dubbing |
| GET | `/v1/dubbing/{dubbing_id}/audio/{language_code}` | audio | Get dubbed audio |
| GET | `/v1/dubbing/{dubbing_id}/transcript/{language_code}` | transcript | Get dubbed transcript |
| GET | `/v1/dubbing/{dubbing_id}/transcripts/{language_code}/format/{format_type}` | transcripts | Retrieve A Transcript |
| GET | `/v1/flows/image` | image | List Image Generations |
| POST | `/v1/flows/image` | image | Create Image Generation |
| GET | `/v1/flows/image/{generation_id}` | image | Get Image Generation |
| GET | `/v1/flows/templates` | templates | List Templates |
| GET | `/v1/flows/templates/{template_id}` | templates | Get Template |
| GET | `/v1/flows/templates/{template_id}/runs` | runs | List Template Runs |
| POST | `/v1/flows/templates/{template_id}/runs` | runs | Create Template Run |
| GET | `/v1/flows/templates/{template_id}/runs/{run_id}` | runs | Get Template Run |
| GET | `/v1/flows/text-to-speech` | textToSpeech | List Speech Generations |
| POST | `/v1/flows/text-to-speech` | textToSpeech | Create Speech Generation |
| GET | `/v1/flows/text-to-speech/{generation_id}` | textToSpeech | Get Speech Generation |
| GET | `/v1/flows/video` | video | List Video Generations |
| POST | `/v1/flows/video` | video | Create Video Generation |
| GET | `/v1/flows/video/{generation_id}` | video | Get Video Generation |
| POST | `/v1/forced-alignment` | forcedAlignment | Create Forced Alignment |
| GET | `/v1/history` | history | Get generated items |
| POST | `/v1/history/download` | history | Download history items |
| GET | `/v1/history/{history_item_id}` | history | Get history item |
| DELETE | `/v1/history/{history_item_id}` | history | Delete history item |
| GET | `/v1/history/{history_item_id}/audio` | history | Get audio from history item |
| GET | `/v1/models` | Models | List models |
| POST | `/v1/music` | music | Compose Music |
| POST | `/v1/music/detailed` | music | Compose Music With A Detailed Response |
| POST | `/v1/music/detailed/stream` | music | Stream Composed Music With A Detailed Response |
| GET | `/v1/music/finetunes` | finetunes | Get Music Finetunes |
| POST | `/v1/music/finetunes` | finetunes | Create Music Finetune |
| GET | `/v1/music/finetunes/{finetune_id}` | finetunes | Get Music Finetune |
| PATCH | `/v1/music/finetunes/{finetune_id}` | finetunes | Update Music Finetune |
| DELETE | `/v1/music/finetunes/{finetune_id}` | finetunes | Delete Music Finetune |
| POST | `/v1/music/plan` | compositionPlan | Generate Composition Plan |
| POST | `/v1/music/stem-separation` | music | Stem Separation |
| POST | `/v1/music/stream` | music | Stream Composed Music |
| POST | `/v1/music/upload` | music | Upload Music |
| POST | `/v1/music/video-to-music` | music | Video To Music |
| GET | `/v1/pronunciation-dictionaries` | pronunciationDictionaries | List pronunciation dictionaries |
| POST | `/v1/pronunciation-dictionaries/add-from-file` | pronunciationDictionaries | Create a pronunciation dictionary from a file |
| POST | `/v1/pronunciation-dictionaries/add-from-rules` | pronunciationDictionaries | Create a pronunciation dictionary from rules |
| GET | `/v1/pronunciation-dictionaries/{dictionary_id}/{version_id}/download` | pronunciationDictionaries | Get pronunciation dictionary by version |
| GET | `/v1/pronunciation-dictionaries/{pronunciation_dictionary_id}` | pronunciationDictionaries | Get pronunciation dictionary |
| PATCH | `/v1/pronunciation-dictionaries/{pronunciation_dictionary_id}` | pronunciationDictionaries | Update Pronunciation Dictionary |
| POST | `/v1/pronunciation-dictionaries/{pronunciation_dictionary_id}/add-rules` | rules | Add pronunciation dictionary rules |
| POST | `/v1/pronunciation-dictionaries/{pronunciation_dictionary_id}/remove-rules` | rules | Remove pronunciation dictionary rules |
| POST | `/v1/pronunciation-dictionaries/{pronunciation_dictionary_id}/set-rules` | rules | Set pronunciation dictionary rules |
| GET | `/v1/service-accounts` | serviceAccounts | Get service accounts |
| POST | `/v1/service-accounts` | serviceAccounts | Create Service Account |
| GET | `/v1/service-accounts/{service_account_user_id}/api-keys` | apiKeys | Get API keys |
| POST | `/v1/service-accounts/{service_account_user_id}/api-keys` | apiKeys | Create API key |
| PATCH | `/v1/service-accounts/{service_account_user_id}/api-keys/{api_key_id}` | apiKeys | Update API key |
| DELETE | `/v1/service-accounts/{service_account_user_id}/api-keys/{api_key_id}` | apiKeys | Delete API key |
| POST | `/v1/service-accounts/{service_account_user_id}/api-keys/{api_key_id}/disable` | apiKeys | Disable Service Account Api Key |
| GET | `/v1/shared-voices` | voices | Get shared voices |
| POST | `/v1/similar-voices` | voices | List similar voices |
| POST | `/v1/single-use-token/{token_type}` | singleUse | Create Single Use Token |
| POST | `/v1/sound-generation` | textToSoundEffects | Create sound effect |
| GET | `/v1/speech-engine` | speechEngine | List Speech Engines |
| POST | `/v1/speech-engine` | speechEngine | Create Speech Engine |
| GET | `/v1/speech-engine/{speech_engine_id}` | speechEngine | Get Speech Engine |
| PATCH | `/v1/speech-engine/{speech_engine_id}` | speechEngine | Update Speech Engine |
| DELETE | `/v1/speech-engine/{speech_engine_id}` | speechEngine | Delete Speech Engine |
| POST | `/v1/speech-engine/{speech_engine_id}/duplicate` | speechEngine | Duplicate Speech Engine |
| POST | `/v1/speech-to-text` | speechToText | Create transcript |
| GET | `/v1/speech-to-text/transcripts/{transcription_id}` | transcripts | Get Transcript By Id |
| DELETE | `/v1/speech-to-text/transcripts/{transcription_id}` | transcripts | Delete Transcript By Id |
| POST | `/v1/studio/podcasts` | studio | Create Podcast |
| GET | `/v1/studio/projects` | projects | List Studio Projects |
| POST | `/v1/studio/projects` | projects | Create Studio Project |
| GET | `/v1/studio/projects/{project_id}` | projects | Get Studio Project |
| POST | `/v1/studio/projects/{project_id}` | projects | Update Studio Project |
| DELETE | `/v1/studio/projects/{project_id}` | projects | Delete Studio Project |
| GET | `/v1/studio/projects/{project_id}/chapters` | chapters | List Chapters |
| POST | `/v1/studio/projects/{project_id}/chapters` | chapters | Create Chapter |
| GET | `/v1/studio/projects/{project_id}/chapters/{chapter_id}` | chapters | Get Chapter |
| POST | `/v1/studio/projects/{project_id}/chapters/{chapter_id}` | chapters | Update Chapter |
| DELETE | `/v1/studio/projects/{project_id}/chapters/{chapter_id}` | chapters | Delete Chapter |
| POST | `/v1/studio/projects/{project_id}/chapters/{chapter_id}/convert` | chapters | Convert Chapter |
| GET | `/v1/studio/projects/{project_id}/chapters/{chapter_id}/snapshots` | snapshots | List Chapter Snapshots |
| GET | `/v1/studio/projects/{project_id}/chapters/{chapter_id}/snapshots/{chapter_snapshot_id}` | snapshots | Get Chapter Snapshot |
| POST | `/v1/studio/projects/{project_id}/chapters/{chapter_id}/snapshots/{chapter_snapshot_id}/stream` | snapshots | Stream Chapter Audio |
| POST | `/v1/studio/projects/{project_id}/content` | content | Update Studio Project Content |
| POST | `/v1/studio/projects/{project_id}/convert` | projects | Convert Studio Project |
| GET | `/v1/studio/projects/{project_id}/muted-tracks` | projects | Get Project Muted Tracks |
| POST | `/v1/studio/projects/{project_id}/pronunciation-dictionaries` | pronunciationDictionaries | Create Pronunciation Dictionaries |
| GET | `/v1/studio/projects/{project_id}/snapshots` | snapshots | List Studio Project Snapshots |
| GET | `/v1/studio/projects/{project_id}/snapshots/{project_snapshot_id}` | snapshots | Get Project Snapshot |
| POST | `/v1/studio/projects/{project_id}/snapshots/{project_snapshot_id}/archive` | snapshots | Stream Archive With Studio Project Audio |
| POST | `/v1/studio/projects/{project_id}/snapshots/{project_snapshot_id}/stream` | snapshots | Stream Studio Project Audio |
| POST | `/v1/text-to-dialogue` | textToDialogue | Create dialogue |
| POST | `/v1/text-to-dialogue/stream` | textToDialogue | Stream dialogue |
| POST | `/v1/text-to-dialogue/stream/with-timestamps` | textToDialogue | Text To Dialogue Streaming With Timestamps |
| POST | `/v1/text-to-dialogue/with-timestamps` | textToDialogue | Text To Dialogue With Timestamps |
| POST | `/v1/text-to-speech/{voice_id}` | textToSpeech | Create speech |
| POST | `/v1/text-to-speech/{voice_id}/stream` | textToSpeech | Stream speech |
| POST | `/v1/text-to-speech/{voice_id}/stream/with-timestamps` | textToSpeech | Stream speech with timing |
| POST | `/v1/text-to-speech/{voice_id}/with-timestamps` | textToSpeech | Create speech with timing |
| POST | `/v1/text-to-voice` | textToVoice | Create A New Voice From Voice Preview |
| POST | `/v1/text-to-voice/create-previews` | textToVoice | Voice design |
| POST | `/v1/text-to-voice/design` | textToVoice | Design A Voice. |
| GET | `/v1/text-to-voice/{generated_voice_id}/stream` | preview | Text To Voice Preview Streaming |
| POST | `/v1/text-to-voice/{voice_id}/remix` | textToVoice | Remix A Voice. |
| GET | `/v1/usage/character-stats` | usage | Get character usage metrics |
| GET | `/v1/user` | user | Get user |
| GET | `/v1/user/subscription` | subscription | Get user subscription |
| POST | `/v1/voice-changer/{voice_id}` | speechToSpeech | Voice changer |
| POST | `/v1/voice-changer/{voice_id}/stream` | speechToSpeech | Voice changer stream |
| GET | `/v1/voices` | voices | List voices |
| GET | `/v1/voices/accents` | accents | Get Voice Accents |
| POST | `/v1/voices/add` | ivc | Create voice clone |
| POST | `/v1/voices/add/{public_user_id}/{voice_id}` | voices | Add shared voice |
| GET | `/v1/voices/collections` | collections | List Voice Collections |
| POST | `/v1/voices/collections` | collections | Create Voice Collection |
| GET | `/v1/voices/collections/{collection_id}` | collections | Get Voice Collection |
| PATCH | `/v1/voices/collections/{collection_id}` | collections | Update Voice Collection |
| DELETE | `/v1/voices/collections/{collection_id}` | collections | Delete Voice Collection |
| POST | `/v1/voices/collections/{collection_id}/voice/{voice_id}` | collections | Add Voice To Collection |
| DELETE | `/v1/voices/collections/{collection_id}/voice/{voice_id}` | collections | Remove Voice From Collection |
| POST | `/v1/voices/pvc` | pvc | Create PVC voice |
| POST | `/v1/voices/pvc/{voice_id}` | pvc | Edit Pvc Voice |
| GET | `/v1/voices/pvc/{voice_id}/captcha` | captcha | Get Pvc Voice Captcha |
| POST | `/v1/voices/pvc/{voice_id}/captcha` | captcha | Verify Pvc Voice Captcha |
| POST | `/v1/voices/pvc/{voice_id}/samples` | samples | Add Samples To Pvc Voice |
| POST | `/v1/voices/pvc/{voice_id}/samples/{sample_id}` | samples | Update Pvc Voice Sample |
| DELETE | `/v1/voices/pvc/{voice_id}/samples/{sample_id}` | samples | Delete Pvc Voice Sample |
| GET | `/v1/voices/pvc/{voice_id}/samples/{sample_id}/audio` | audio | Retrieve Voice Sample Audio |
| POST | `/v1/voices/pvc/{voice_id}/samples/{sample_id}/separate-speakers` | speakers | Start Speaker Separation |
| GET | `/v1/voices/pvc/{voice_id}/samples/{sample_id}/speakers` | speakers | Retrieve Speaker Separation Status |
| GET | `/v1/voices/pvc/{voice_id}/samples/{sample_id}/speakers/{speaker_id}/audio` | audio | Retrieve Separated Speaker Audio |
| GET | `/v1/voices/pvc/{voice_id}/samples/{sample_id}/waveform` | waveform | Retrieve Voice Sample Visual Waveform |
| POST | `/v1/voices/pvc/{voice_id}/train` | pvc | Run Pvc Training |
| POST | `/v1/voices/pvc/{voice_id}/verification` | verification | Request Manual Verification |
| GET | `/v1/voices/settings/default` | settings | Get default voice settings |
| GET | `/v1/voices/{voice_id}` | voices | Get voice |
| DELETE | `/v1/voices/{voice_id}` | voices | Delete voice |
| POST | `/v1/voices/{voice_id}/edit` | voices | Edit voice |
| POST | `/v1/voices/{voice_id}/replicate-to-isolated-environment` | voices | Replicate Voice To Isolated Environment |
| DELETE | `/v1/voices/{voice_id}/samples/{sample_id}` | Samples | Delete voice sample |
| GET | `/v1/voices/{voice_id}/samples/{sample_id}/audio` | audio | Get audio from sample |
| GET | `/v1/voices/{voice_id}/settings` | settings | Get voice settings |
| POST | `/v1/voices/{voice_id}/settings/edit` | settings | Edit voice settings |
| POST | `/v1/workspace/analytics/query/usage-by-product-over-time` | usage | Get Workspace Usage |
| POST | `/v1/workspace/analytics/requests` | requests | List Api Requests |
| POST | `/v1/workspace/analytics/usage` | usage | Get Workspace Cost Usage |
| GET | `/v1/workspace/audit-logs` | auditLogs | Get Workspace Audit Logs |
| GET | `/v1/workspace/auth-connections` | authConnections | Get Workspace Auth Connections |
| POST | `/v1/workspace/auth-connections` | authConnections | Create Workspace Auth Connection |
| PATCH | `/v1/workspace/auth-connections/{auth_connection_id}` | authConnections | Update Workspace Auth Connection |
| DELETE | `/v1/workspace/auth-connections/{auth_connection_id}` | authConnections | Delete Workspace Auth Connection |
| GET | `/v1/workspace/groups` | groups | List workspace groups |
| GET | `/v1/workspace/groups/search` | groups | Search user group |
| POST | `/v1/workspace/groups/{group_id}/members` | members | Add member to user group |
| POST | `/v1/workspace/groups/{group_id}/members/remove` | members | Remove member from user group |
| DELETE | `/v1/workspace/invites` | invites | Delete invite |
| POST | `/v1/workspace/invites/add` | invites | Invite user |
| POST | `/v1/workspace/invites/add-bulk` | invites | Invite Multiple Users |
| GET | `/v1/workspace/members` | members | Get Workspace Members |
| POST | `/v1/workspace/members` | members | Update member |
| PUT | `/v1/workspace/members/{user_id}/usage-limit` | members | Update Member Usage Limit |
| GET | `/v1/workspace/resources/{resource_id}` | resources | Get Resource |
| POST | `/v1/workspace/resources/{resource_id}/share` | resources | Share Workspace Resource |
| POST | `/v1/workspace/resources/{resource_id}/unshare` | resources | Unshare Workspace Resource |
| GET | `/v1/workspace/webhooks` | webhooks | List Workspace Webhooks |
| POST | `/v1/workspace/webhooks` | webhooks | Create Workspace Webhook |
| PATCH | `/v1/workspace/webhooks/{webhook_id}` | webhooks | Update Workspace Webhook |
| DELETE | `/v1/workspace/webhooks/{webhook_id}` | webhooks | Delete Workspace Webhook |
| POST | `/v1/workspace/webhooks/{webhook_id}/deliveries/{delivery_id}/redeliver` | webhooks | Redeliver Webhook Delivery |
| POST | `/v1/workspace/webhooks/{webhook_id}/test` | webhooks | Send Test Webhook Event |
| POST | `/v1/workspaces/api-keys/disable` | apiKeys | Disable API key |
| POST | `/v1/workspaces/api-keys/third-party-disabling` | workspace | Set Workspace Third-Party Disabling Policy |
| GET | `/v2/voices` | voices | List voices |

총 206개 오퍼레이션(convai·reception 제외).
