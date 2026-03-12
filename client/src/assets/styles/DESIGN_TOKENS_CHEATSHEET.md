# Design Tokens Quick Reference

> **Keep this open while coding.** All values reference [`variables.css`](./variables.css)

---

## 🎨 Colors

### Surfaces (Backgrounds)
```css
--surface-base           /* Page background */
--surface-raised         /* Cards, panels */
--surface-elevated       /* Modals, dialogs */
--surface-overlay        /* Dropdowns, tooltips */
--surface-interactive    /* Hover states */
--surface-hover          /* Active hover states */
```

### Semantic
```css
--color-success          /* Green: #10b981 */
--color-warning          /* Orange: #f59e0b */
--color-error            /* Red: #ef4444 */
--color-info             /* Cyan: #06b6d4 */
--color-primary          /* Gray: #636363 */
```

### Text
```css
--color-text-primary     /* Main content */
--color-text-secondary   /* Supporting text */
--color-text-tertiary    /* De-emphasized */
--color-text-muted       /* Disabled/subtle */
```

### Borders
```css
--color-border-light     /* #444444 */
--color-border-medium    /* #444444 */
--color-border-focus     /* Primary color */
```

### Alpha Overlays
```css
--color-success-alpha-10    /* 10% opacity */
--color-success-alpha-20    /* 20% opacity */
--color-error-alpha-10      /* 10% opacity */
--color-warning-alpha-10    /* 10% opacity */
```

---

## 📏 Spacing

```css
--spacing-2xs     /* 2px  - Fine details */
--spacing-xs      /* 4px  - Minimal */
--spacing-sm      /* 8px  - Tight */
--spacing-md      /* 16px - Standard */
--spacing-lg      /* 24px - Comfortable (DEFAULT card) */
--spacing-xl      /* 32px - Large */
--spacing-2xl     /* 48px - Extra large */
--spacing-3xl     /* 64px - Maximum */
```

**Common Uses:**
- Button gap: `--spacing-sm` (8px)
- Form groups: `--spacing-md` (16px)
- Card padding: `--spacing-lg` (24px)
- Modal padding: `--spacing-xl` (32px)

---

## 📝 Typography

### Sizes
```css
--font-size-xs      /* 12px - Captions */
--font-size-sm      /* 14px - Small labels */
--font-size-base    /* 16px - Body (DEFAULT) */
--font-size-lg      /* 18px - Emphasized */
--font-size-xl      /* 20px - h4 */
--font-size-2xl     /* 24px - h3 */
--font-size-3xl     /* 30px - h2 */
--font-size-4xl     /* 36px - h1 */
--font-size-5xl     /* 48px - Display */
```

### Weights
```css
--font-weight-normal      /* 400 - Body */
--font-weight-medium      /* 500 - Labels */
--font-weight-semibold    /* 600 - Headings */
--font-weight-bold        /* 700 - Strong */
```

---

## 🌊 Elevation (Shadows)

```css
--shadow-sm         /* Subtle - Cards */
--shadow-md         /* Raised - Dropdowns */
--shadow-lg         /* Elevated - Modals */
--shadow-xl         /* Floating - Alerts */
--shadow-focus      /* Focus rings */
--shadow-glow       /* Primary emphasis */
```

---

## 🔘 Border Radius

```css
--radius-sm      /* 6px  - Badges */
--radius-md      /* 8px  - Inputs, buttons */
--radius-lg      /* 12px - Cards (DEFAULT) */
--radius-xl      /* 16px - Large containers */
--radius-full    /* 9999px - Pills, circles */
```

---

## 🔴 Buttons

### Sizes
```css
/* Small (32px) */
height: var(--btn-height-sm);
padding: 0 var(--btn-padding-x-sm);
font-size: var(--btn-font-size-sm);

/* Medium (40px) - DEFAULT */
height: var(--btn-height-md);
padding: 0 var(--btn-padding-x-md);
font-size: var(--btn-font-size-md);

/* Large (48px) */
height: var(--btn-height-lg);
padding: 0 var(--btn-padding-x-lg);
font-size: var(--btn-font-size-lg);
```

### Border Radius
```css
border-radius: var(--btn-border-radius); /* 8px */
```

---

## 📋 Form Inputs

### Sizes
```css
/* Small (32px) */
height: var(--input-height-sm);
padding: 0 var(--input-padding-x-sm);

/* Medium (40px) - DEFAULT */
height: var(--input-height-md);
padding: 0 var(--input-padding-x-md);

/* Large (48px) */
height: var(--input-height-lg);
padding: 0 var(--input-padding-x-lg);
```

### States
```css
/* Default */
border: 1px solid var(--color-border-light);
background: var(--surface-interactive);

/* Focus */
border-color: var(--color-border-focus);
box-shadow: var(--shadow-focus);

/* Error */
border-color: var(--color-error);
```

---

## 🃏 Cards

```css
/* Standard card */
background: var(--card-background);
padding: var(--card-padding-md);        /* 24px */
border-radius: var(--card-border-radius); /* 12px */
border: 1px solid var(--card-border-color);
box-shadow: var(--shadow-sm);

/* Card header */
padding-bottom: var(--spacing-md);
border-bottom: 1px solid var(--color-border-light);
```

---

## 🪟 Modals

```css
/* Backdrop */
background: var(--modal-backdrop);
z-index: var(--z-modal-backdrop);

/* Modal */
background: var(--modal-background);
padding: var(--modal-padding);          /* 32px */
border-radius: var(--modal-border-radius); /* 12px */
box-shadow: var(--modal-shadow);
z-index: var(--z-modal);
```

---

## 📊 Z-Index Scale

```css
--z-dropdown: 1000
--z-sticky: 1020
--z-fixed: 1030
--z-modal-backdrop: 1040
--z-modal: 1050
--z-popover: 1060
--z-tooltip: 1070
```

---

## ⚡ Transitions

```css
--transition-fast    /* 150ms - Micro-interactions */
--transition-base    /* 200ms - DEFAULT */
--transition-slow    /* 300ms - Large movements */
```

---

## 💡 Copy-Paste Snippets

### Button
```css
.btn {
  height: var(--btn-height-md);
  padding: 0 var(--btn-padding-x-md);
  font-size: var(--btn-font-size-md);
  font-weight: var(--font-weight-semibold);
  border-radius: var(--btn-border-radius);
  background: var(--color-primary);
  color: white;
  transition: var(--transition-base);
}
```

### Input
```css
.input {
  height: var(--input-height-md);
  padding: 0 var(--input-padding-x-md);
  font-size: var(--input-font-size-md);
  border-radius: var(--input-border-radius);
  border: 1px solid var(--color-border-light);
  background: var(--surface-interactive);
  color: var(--color-text-primary);
}

.input:focus {
  outline: none;
  border-color: var(--color-border-focus);
  box-shadow: var(--shadow-focus);
}
```

### Card
```css
.card {
  background: var(--card-background);
  padding: var(--card-padding-md);
  border-radius: var(--card-border-radius);
  border: 1px solid var(--card-border-color);
  box-shadow: var(--shadow-sm);
}
```

### Success Message
```css
.success {
  background: var(--color-success-alpha-10);
  color: var(--color-success);
  border: 1px solid var(--color-success);
  padding: var(--spacing-md);
  border-radius: var(--radius-md);
}
```

---

## ❌ Don't Do This

```css
/* ❌ Hardcoded values */
color: #10b981;
padding: 1.35rem;
font-size: 0.95rem;
box-shadow: 0 4px 12px rgba(0,0,0,0.2);

/* ✅ Use tokens */
color: var(--color-success);
padding: var(--spacing-lg);
font-size: var(--font-size-base);
box-shadow: var(--shadow-md);
```

---

**Full Documentation:** [DESIGN_SYSTEM.md](./DESIGN_SYSTEM.md)  
**Token Definitions:** [variables.css](./variables.css)
