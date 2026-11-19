# License and third-party audit

The EpochGuard repository's original code is licensed under [Apache-2.0](../LICENSE). The grant applies to the project authors' licensable contributions, not to third-party code under different terms. Redistribution still requires satisfying the respective third-party licenses and applicable notices.

**Chosen repository license: Apache-2.0.** Its explicit patent grant and notice terms suit a gateway extension and align with Bifrost. This choice is not a certification of third-party redistribution clearance; authorship/permission and dependency notice obligations remain important.

## Inspected material

| Material | Inspected license or status | Distribution implication |
| --- | --- | --- |
| [Pinned Bifrost](https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/LICENSE) | Apache-2.0 | Preserve license, applicable notices and attribution; no tracked upstream source patch is made |
| Go toolchain / standard library | BSD-style Go license in the pinned toolchain image | Retain applicable notices when redistributing binaries/images |
| React / React DOM 19.3.1 | MIT, locked npm package metadata | Runtime frontend redistribution needs the applicable license/copyright notice |
| Vite 8.3.8 / Vitest 5.1.0 / Testing Library React 16.3.3 | MIT | Build/test dependencies also have notice obligations when distributed |
| TypeScript 7.0.2 / Playwright 1.65.1 | Apache-2.0 | Build/test tooling; browser distributions have their own notices |
| Full npm lock | 150 packages: MIT 99, Apache-2.0 28, MPL-2.0 12, other permissive/CC0 licenses 11 | Metadata inventory is not a file-level legal audit; inspect transitive MPL files and distributed bundles before release |
| Python and Go transitive dependencies / Alpine and Debian image packages | Pinned graphs/lock files; heterogeneous upstream licenses | Complete binary/image attribution and license inventory remain a distribution prerequisite |
| Lab artwork and interface assets | Repository-owned SVG/CSS/UI; no stock photography, copied upstream dashboard or external font service | Project licensing decision still applies; the API-only embed placeholder is identified in the Dockerfile |

The npm count is from `web/lab/package-lock.json` license metadata at the 005B baseline, including development dependencies, not an inventory of code actually shipped in the browser bundle. No missing npm license fields were observed. The repository does not bundle upstream dashboard assets. OS/toolchain dependencies can differ in obligations from application source.

This audit does not certify redistribution clearance or generate complete third-party notices for every compiled dependency. Before distributing an image/binary, inventory its actual compiled Go modules, installed Python/OS packages and bundled JS assets, retain their exact license/copyright/NOTICE files, and address any source-offer obligations. No automated release or image publication is added here.
