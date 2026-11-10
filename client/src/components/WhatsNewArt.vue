<template>
  <svg
    :viewBox="`0 0 320 ${height}`"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    font-family="system-ui, -apple-system, 'Segoe UI', sans-serif"
    font-size="12"
    font-weight="600"
    aria-hidden="true"
  >
    <!-- flow: where something goes (source -> optional detour -> targets) -->
    <template v-if="art.type === 'flow'">
      <g v-if="flow.poster">
        <rect x="10" y="26" width="76" height="118" rx="12" fill="currentColor" fill-opacity=".16" />
        <path d="M38 62l22 13-22 13z" fill="currentColor" fill-opacity=".5" />
        <path d="M24 110h48M24 124h30" stroke-opacity=".6" />
      </g>
      <g v-else>
        <rect x="8" y="54" width="86" height="62" rx="14" fill="currentColor" fill-opacity=".16" />
        <path d="M37 74l6 6 12-13" stroke-width="2.5" />
        <text x="51" y="104" text-anchor="middle" fill="currentColor" stroke="none">{{ flow.sourceLabel }}</text>
      </g>

      <g v-if="art.via">
        <rect x="126" y="14" width="70" height="34" rx="11" fill="currentColor" fill-opacity=".07" stroke-opacity=".55" />
        <text x="161" y="35" text-anchor="middle" fill="currentColor" fill-opacity=".75" stroke="none">{{ art.via }}</text>
        <path d="M94 76C112 76 108 31 126 31" stroke-opacity=".5" stroke-dasharray="4 5" />
        <path :d="`M196 31h${flow.groupX - 196}`" stroke-opacity=".5" stroke-dasharray="4 5" />
      </g>

      <rect v-if="flow.group" :x="flow.group.x" :y="flow.group.y" :width="flow.group.w" :height="flow.group.h" rx="16" fill="currentColor" fill-opacity=".1" stroke-opacity=".4" />
      <g v-for="(box, i) in flow.boxes" :key="i">
        <rect :x="flow.boxX" :y="box.y" :width="flow.boxW" :height="box.h" rx="14" fill="currentColor" fill-opacity=".16" />
        <template v-if="flow.compact">
          <text :x="flow.boxX + flow.boxW / 2" :y="box.y + box.h / 2 + 4" text-anchor="middle" fill="currentColor" stroke="none">{{ box.label }}</text>
        </template>
        <template v-else>
          <text :x="flow.boxX + 16" :y="box.y + box.h / 2 + (box.sub ? -2 : 5)" font-size="13" font-weight="700" fill="currentColor" stroke="none">{{ box.label }}</text>
          <text v-if="box.sub" :x="flow.boxX + 16" :y="box.y + box.h / 2 + 16" font-size="11" fill="currentColor" fill-opacity=".7" stroke="none">{{ box.sub }}</text>
          <template v-if="box.done">
            <circle :cx="flow.boxX + flow.boxW - 24" :cy="box.y + box.h / 2" r="13" fill="currentColor" fill-opacity=".9" stroke="none" />
            <path :d="`M${flow.boxX + flow.boxW - 31} ${box.y + box.h / 2}l5 5 9-10`" stroke="var(--color-panel, #0b0d12)" stroke-width="3" />
          </template>
        </template>
      </g>

      <path :d="`M${flow.arrowFrom} ${flow.arrowY}H${flow.arrowTo}`" stroke-width="3" />
      <path :d="`M${flow.arrowTo - 10} ${flow.arrowY - 10}l10 10-10 10`" stroke-width="3" />
      <text v-if="art.arrow" :x="(flow.arrowFrom + flow.arrowTo) / 2" :y="flow.arrowY - 12" text-anchor="middle" font-size="10" fill="currentColor" fill-opacity=".75" stroke="none">{{ art.arrow }}</text>
      <g v-if="art.badge">
        <rect :x="(flow.arrowFrom + flow.arrowTo) / 2 - 26" :y="flow.arrowY + 12" width="52" height="22" rx="11" fill="currentColor" fill-opacity=".9" stroke="none" />
        <text :x="(flow.arrowFrom + flow.arrowTo) / 2" :y="flow.arrowY + 27" text-anchor="middle" fill="var(--color-panel, #0b0d12)" stroke="none" font-size="11" font-weight="800">{{ art.badge }}</text>
      </g>
    </template>

    <!-- form: a miniature of the settings being described -->
    <template v-else-if="art.type === 'form'">
      <rect x="20" y="8" width="280" height="154" rx="16" fill="currentColor" fill-opacity=".08" stroke-opacity=".5" />
      <g v-for="(field, i) in form.fields" :key="i">
        <text x="38" :y="form.rowY(i)" fill="currentColor" fill-opacity=".7" stroke="none" font-size="10">{{ field.label.toUpperCase() }}</text>
        <rect x="38" :y="form.rowY(i) + 6" width="244" height="28" rx="9" fill="currentColor" fill-opacity=".14" />
        <text x="52" :y="form.rowY(i) + 25" fill="currentColor" stroke="none">{{ field.value }}</text>
        <path :d="`M262 ${form.rowY(i) + 17}l5 5 5-5`" />
      </g>
      <g v-if="art.optional">
        <path d="M50 142l2.4 5.2 5.6.6-4.2 3.8 1.2 5.6-5-2.8-5 2.8 1.2-5.6-4.2-3.8 5.6-.6z" fill="currentColor" stroke="none" transform="translate(0 -6)" />
        <text x="70" y="147" fill="currentColor" stroke="none">{{ art.optional.label }}</text>
        <rect x="124" y="132" width="158" height="24" rx="9" stroke-dasharray="4 4" stroke-opacity=".6" />
        <text x="138" y="148" fill="currentColor" fill-opacity=".65" stroke="none" font-size="11">{{ art.optional.value }}</text>
        <path d="M262 141l5 5 5-5" stroke-opacity=".6" />
      </g>
    </template>

    <!-- features: a grid of capabilities, locked or available -->
    <template v-else-if="art.type === 'features'">
      <g v-for="(chip, i) in features.chips" :key="i">
        <rect :x="chip.x" :y="chip.y" width="144" height="56" rx="14" fill="currentColor" fill-opacity=".07" stroke-opacity=".6" />
        <text :x="chip.x + 40" :y="chip.y + 25" fill="currentColor" fill-opacity=".85" stroke="none" font-size="12" font-weight="700">{{ chip.label }}</text>
        <text v-if="chip.sub" :x="chip.x + 40" :y="chip.y + 41" fill="currentColor" fill-opacity=".55" stroke="none" font-size="10">{{ chip.sub }}</text>
        <template v-if="features.locked">
          <rect :x="chip.x + 12" :y="chip.y + 22" width="16" height="14" rx="3" fill="currentColor" fill-opacity=".25" stroke-opacity=".8" />
          <path :d="`M${chip.x + 15} ${chip.y + 22}v-4a5 5 0 0 1 10 0v4`" stroke-opacity=".8" />
        </template>
        <template v-else>
          <circle :cx="chip.x + 21" :cy="chip.y + 28" r="9" fill="currentColor" fill-opacity=".9" stroke="none" />
          <path :d="`M${chip.x + 16.5} ${chip.y + 28}l3.5 3.5 6-7`" stroke="var(--color-panel, #0b0d12)" stroke-width="2.5" />
        </template>
      </g>
    </template>
  </svg>
</template>

<script>
/**
 * Illustration for a "What's new" slide, drawn from data so a release needs no new image files.
 * Types (see utils/whatsNew.js `artProblems` for the exact shape of each):
 *  - flow:     `{ type, source: {label} | {poster: true}, via?, targets: [{label, sub?, done?}], arrow?, badge? }`
 *  - form:     `{ type, fields: [{label, value}], optional?: {label, value} }`
 *  - features: `{ type, items: [{label, sub?}], locked? }`
 * Everything is drawn with `currentColor`, so the slide's tone tints it in both themes.
 */
export default {
  name: 'WhatsNewArt',
  props: {
    art: { type: Object, required: true },
  },
  computed: {
    flow() {
      const art = this.art;
      const targets = (art.targets || []).slice(0, 3);
      const compact = !!art.via; // the detour leaves room for narrow target boxes only
      const boxX = compact ? 238 : 180;
      const boxW = compact ? 70 : 120;
      const gap = 10;
      const boxH = Math.min(62, (146 - gap * (targets.length - 1)) / targets.length);
      const stack = targets.length * boxH + gap * (targets.length - 1);
      const top = 85 - stack / 2;
      const group = targets.length > 1 ? { x: boxX - 10, y: top - 10, w: boxW + 20, h: stack + 20 } : null;
      const arrowY = compact ? 100 : 85;
      return {
        poster: !!art.source?.poster,
        sourceLabel: art.source?.label || '',
        compact,
        boxX,
        boxW,
        boxes: targets.map((target, i) => ({ ...target, y: top + i * (boxH + gap), h: boxH })),
        group,
        groupX: group ? group.x : boxX - 8,
        arrowFrom: 98,
        arrowTo: (group ? group.x : boxX) - 6,
        arrowY,
      };
    },
    form() {
      const fields = (this.art.fields || []).slice(0, this.art.optional ? 2 : 3);
      // The last select must end above the optional row (or the panel's bottom edge).
      const end = this.art.optional ? 128 : 156;
      const step = fields.length > 1 ? Math.min(56, (end - 64) / (fields.length - 1)) : 56;
      return { fields, rowY: (i) => 30 + i * step };
    },
    features() {
      const items = (this.art.items || []).slice(0, 6);
      return {
        locked: this.art.locked !== false,
        // A chip alone on its row (odd count) sits centred under the pair above.
        chips: items.map((item, i) => ({ ...item, x: i % 2 ? 164 : i === items.length - 1 ? 88 : 12, y: 20 + Math.floor(i / 2) * 74 })),
      };
    },
    height() {
      if (this.art.type !== 'features') return 170;
      return 40 + Math.ceil(Math.min((this.art.items || []).length, 6) / 2) * 56 + (Math.ceil(Math.min((this.art.items || []).length, 6) / 2) - 1) * 18;
    },
  },
};
</script>
