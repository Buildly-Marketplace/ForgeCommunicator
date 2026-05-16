# ForgeCommunicator + ForgeInboxLite Integration Blueprint

## Goal
Build one native macOS app with a top-level ForgeCommunicator shell that can host multiple provider sessions (Communicator, WhatsApp Web, Signal), while matching the Communicator web visual language as closely as possible.

## Non-Goals (Phase 1)
- No backend protocol changes for WhatsApp or Signal.
- No cloud sync for local source metadata.
- No rewrite of Communicator API contracts.

## Existing Assets to Reuse
- Communicator-native stack now lives in the combined app under native/Sources/ForgeInboxLite.
- Communicator visual tokens now live in native/Sources/ForgeInboxLite/UI.
- InboxLite multi-session shell and local encrypted config:
  - native/Sources/ForgeInboxLite/Views/ContentView.swift
  - native/Sources/ForgeInboxLite/Services/AccountStore.swift
  - native/Sources/ForgeInboxLite/Services/EncryptedConfigStore.swift
  - native/Sources/ForgeInboxLite/Web/AccountWebContainerView.swift
- Web visual language source of truth:
  - app/templates/layout.html
  - app/templates/auth/login.html
  - app/templates/channels/view.html
  - app/brand.py

## Target Architecture
### 1) Host Shell
Create a single root shell named ForgeCommunicatorShell with provider-driven navigation.

Primary regions:
- Left rail: Source list (Communicator/WhatsApp/Signal) + add source
- Main workspace: provider content area
- Right contextual panel: provider-specific details (thread, profile, controls)

### 2) Source Domain Model
Replace account-only model with a provider-agnostic Source model.

Proposed fields:
- id: UUID
- sourceType: communicator | whatsapp | signal
- displayName: String
- profilePath: String
- createdAt: Date
- lastOpenedAt: Date?
- providerConfig: Data (encrypted JSON)
- authRef: String? (keychain lookup key)
- sortOrder: Int

### 3) Provider Contracts
Define one protocol per source implementation.

Provider contract (high-level):
- open(source)
- close(source)
- renderMainView(source)
- renderToolbar(source)
- renderInspector(source)
- supportsUnreadCount
- supportsSearch

Implementations:
- CommunicatorProvider: wraps existing APIClient + WebSocketService + viewmodels
- WhatsAppProvider: wraps WebSessionManager and account web container
- SignalProvider: wraps SignalLauncher and profile controls

### 4) Shared Styling System (Critical)
Promote one native styling package built from Communicator web tokens.

Required style primitives:
- ForgeBackgroundLayer: gradient + radial lights + stars + floating particles
- ForgeGlassSurface: blur + low-alpha fill + subtle border
- ForgeHeaderBar: channel/workspace top bar style
- ForgeBadgeIcon: rounded device badge with waveform and three hardware dots
- ForgeListCellStyle: sidebar rows with hover, selected, muted states
- ForgeComposerStyle: input area treatment for message/composer-like panels

## Web-to-Native Visual Parity Spec
Use these values as implementation defaults.

### Color and Surfaces
- Base gradient: #0B0F17 -> #111827 -> #1B2638
- Elevated panel: #2D3A50
- Brand primary: #4DB6FF
- Brand accent: #FFC857
- Text/silver: #E6EAF1
- Dark panel: rgba(17, 24, 39, 0.72) with blur
- Border: rgba(230, 234, 241, 0.08) to 0.12

### Atmosphere Layers
- Radial lights (3 layers):
  - ellipse at 20% 80%, blue glow
  - ellipse at 80% 20%, amber glow
  - ellipse centered, blue/cyan glow
- Twinkling stars texture layer
- Floating particles with 8-node slow drift animation

### Shape and Depth
- Card radius: 12-16
- Glass cards: thin border + soft shadow + backdrop blur
- Device badges: dark metal body, inset navy screen, blue/amber waveform, small hardware dots
- Headers: subtle gradient strip over dark glass base

### Motion
- Low-frequency breathing/float motions only
- Avoid aggressive spring animations
- Keep interaction timing at 150-300ms

### Typography
- Keep SF stack in native, but mirror web hierarchy:
  - Brand/title: Orbitron bold or native monospaced fallback
  - Section title: semibold
  - Body: regular
  - Metadata: caption/secondary

## Phase Plan
## PR1: Foundation and Data Migration (No Major UI Risk)
### Scope
- Introduce Source model and encrypted migration path from existing account config.
- Preserve InboxLite behavior while adding communicator source type support.
- Add shell-level routing scaffolding without replacing all existing views.

### File-Level Changes
1. Add source models and migration
- Add: native/Sources/ForgeInboxLite/Models/Source.swift
- Add: native/Sources/ForgeInboxLite/Models/SourceType.swift
- Add: native/Sources/ForgeInboxLite/Models/PersistedSourceConfig.swift
- Update: native/Sources/ForgeInboxLite/Services/EncryptedConfigStore.swift
- Update: native/Sources/ForgeInboxLite/Services/AccountStore.swift (becomes SourceStore or wraps it)

2. Add provider abstraction
- Add: native/Sources/ForgeInboxLite/Providers/SourceProvider.swift
- Add: native/Sources/ForgeInboxLite/Providers/CommunicatorProvider.swift
- Add: native/Sources/ForgeInboxLite/Providers/WhatsAppProvider.swift
- Add: native/Sources/ForgeInboxLite/Providers/SignalProvider.swift

3. Add shell router
- Add: native/Sources/ForgeInboxLite/Views/Shell/ForgeCommunicatorShellView.swift
- Update: native/Sources/ForgeInboxLite/App/ForgeInboxLiteApp.swift

### Acceptance Criteria
- Existing WhatsApp and Signal sessions still load.
- Existing encrypted config automatically migrates to source schema.
- User can add a Communicator source placeholder.
- No visual regressions in current InboxLite views.

## PR2: Visual Parity and Communicator Embedding
### Scope
- Apply Communicator visual system to shell and core provider screens.
- Embed Communicator native experience under new shell while keeping provider boundaries.

### File-Level Changes
1. Shared visual components
- Add: native/Sources/ForgeInboxLite/UI/ForgeBackgroundLayer.swift
- Add: native/Sources/ForgeInboxLite/UI/ForgeGlassSurface.swift
- Add: native/Sources/ForgeInboxLite/UI/ForgeBadgeIcon.swift
- Add: native/Sources/ForgeInboxLite/UI/ForgeHeaderBar.swift
- Add: native/Sources/ForgeInboxLite/UI/ForgeSidebarRow.swift

2. Theme centralization
- Update: native/Sources/ForgeInboxLite/UI/ForgeTheme.swift

3. Shell visual integration
- Update: native/Sources/ForgeInboxLite/Views/Shell/ForgeCommunicatorShellView.swift
- Update: native/Sources/ForgeInboxLite/Views/ContentView.swift (or replace with shell entry)

4. Communicator provider integration
- Add: native/Sources/ForgeInboxLite/Providers/Communicator/CommunicatorContainerView.swift
- Add: native/Sources/ForgeInboxLite/Providers/Communicator/CommunicatorSessionState.swift
- Reuse from combined native source modules:
  - Services/APIClient.swift
  - Services/WebSocketService.swift
  - ViewModels/ConversationListViewModel.swift
  - ViewModels/ChatViewModel.swift

### Acceptance Criteria
- Main shell background and depth match web Communicator style.
- Sidebar, header, and glass cards visually align with web channels view.
- Communicator source opens native conversations with existing functionality.
- WhatsApp and Signal remain isolated and usable.

## Detailed Design Matching Checklist
Use this before merging PR2:

1. Background parity
- Gradient stop order and contrast feel match app/templates/layout.html.
- Radial atmosphere layers are visible but subtle.
- Star layer has slow twinkle, not static image.

2. Surface parity
- Primary containers are glass-dark style, not flat opaque blocks.
- Borders are low-alpha white, consistently applied.
- Card shadows are soft and directional.

3. Sidebar/header parity
- Left rail badge icon mirrors web communicator badge treatment.
- Header bar has dark glass + border + accent hover states.
- Selected row state uses brand tint and glow-like emphasis.

4. Interaction parity
- Hover states on macOS emulate web hover brightness and border shifts.
- Transition timing remains around 200ms.
- Focus states are visible for keyboard navigation.

## Technical Risks and Mitigations
- Risk: Config migration data loss.
  - Mitigation: Preserve old config.enc backup before first write; add one-time migration marker.
- Risk: Communicator code duplication between ForgeApp and InboxLite.
  - Mitigation: Keep only combined app modules under native/Sources/ForgeInboxLite and avoid reintroducing parallel app trees.
- Risk: Visual mismatch from ad-hoc colors.
  - Mitigation: Ban hardcoded colors in new shell; use theme tokens only.

## Testing Strategy
- Unit:
  - Source migration tests from legacy account config
  - SourceStore add/remove/reorder/select persistence tests
- UI smoke:
  - Launch with 3 sources (Communicator, WhatsApp, Signal)
  - Switch sources repeatedly and verify state isolation
- Visual regression (manual + snapshot):
  - Sidebar, header, glass panel, empty states, and main background

## Suggested Branching
- branch: feat/shell-source-model
- branch: feat/shell-visual-parity

## Immediate Next Actions
1. Implement PR1 schema and migration only.
2. Add shell view scaffolding with placeholder provider rendering.
3. Start PR2 by implementing ForgeBackgroundLayer and ForgeGlassSurface first, then retrofit shell and provider containers.
