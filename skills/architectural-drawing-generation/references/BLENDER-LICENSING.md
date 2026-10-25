# Blender runtime licensing boundary

Gridline's ordinary source files retain the root MIT license and notices. The new
`components_worker.py` Blender API worker and `tests/components_native_acceptance.py`
API acceptance harness are explicitly GPL-2.0-or-later; its
complete corresponding source is shipped, with the full GPL text in `GPL-2.0.txt`.
It imports MIT-licensed Gridline helpers, whose original MIT notices and grants
remain available. The mixed distribution must not be represented as solely MIT.

The external ARCHIMESH implementation, images and bytecode are not bundled.
Users separately obtain the official GPL-2.0-or-later extension. Explicit source
hash approval permits a disposable execution snapshot; it does not install or
patch a user profile. The new worker operates on reviewed data and emits new
artifacts only. Normal Blender output ownership does not clear third-party asset
rights; CC0 asset provenance and live API terms are tracked separately.

The pre-existing `blender_native_worker.py` remains available under MIT, which
permits sublicensing with preservation of its notice. When combining that worker
or other MIT helpers with Blender/GPL runtime code for redistribution, distribute
the combined work under the applicable GPL terms as well, preserving all MIT
notices. This notice does not claim sole ownership of Blender, ARCHIMESH or assets,
change the upstream add-on license, or provide legal certification.

Primary references checked for this implementation:
- https://www.blender.org/support/faq/#using-blender-8
- https://www.gnu.org/licenses/license-list.html#Expat
- https://extensions.blender.org/add-ons/archimesh/

The Blender FAQ describes distributed API scripts as GPL and separately describes
external, non-API controllers. The FSF lists Expat/MIT as GPL-compatible. These
sources support this explicit boundary; they do not substitute for project-specific
qualified legal advice, particularly for downstream proprietary integrations.
