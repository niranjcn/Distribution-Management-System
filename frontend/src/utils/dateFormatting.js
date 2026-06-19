const pad2 = (value) => String(value).padStart(2, '0');

const formatDate = (date) => {
  const day = pad2(date.getDate());
  const month = pad2(date.getMonth() + 1);
  const year = date.getFullYear();
  return `${day}/${month}/${year}`;
};

const formatDateTime = (date) => {
  const hours = pad2(date.getHours());
  const minutes = pad2(date.getMinutes());
  return `${formatDate(date)} ${hours}:${minutes}`;
};

export const installGlobalDateFormatting = () => {
  if (globalThis.__dmsDateFormattingInstalled) return;
  globalThis.__dmsDateFormattingInstalled = true;

  const originalToLocaleDateString = Date.prototype.toLocaleDateString;
  const originalToLocaleString = Date.prototype.toLocaleString;

  Date.prototype.toLocaleDateString = function patchedToLocaleDateString(...args) {
    if (args.length > 0) {
      return originalToLocaleDateString.apply(this, args);
    }
    if (Number.isNaN(this.getTime())) {
      return originalToLocaleDateString.apply(this, args);
    }
    return formatDate(this);
  };

  Date.prototype.toLocaleString = function patchedToLocaleString(...args) {
    if (args.length > 0) {
      return originalToLocaleString.apply(this, args);
    }
    if (Number.isNaN(this.getTime())) {
      return originalToLocaleString.apply(this, args);
    }
    return formatDateTime(this);
  };
};
