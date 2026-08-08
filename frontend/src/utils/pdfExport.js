import jsPDF from 'jspdf';

/**
 * Export a table to a PDF document.
 *
 * @param {Object} options
 * @param {string} options.title       Report title (e.g. "Sub Distribution Report — Total")
 * @param {string} options.subtitle    Optional subtitle line (filters applied, etc.)
 * @param {Array<{header: string, key?: string, render?: (row: any) => any}>} options.columns
 *        Column definitions. Use `render` for computed/formatted cells, otherwise `key`.
 * @param {Array<any>} options.rows    Data rows (already filtered).
 * @param {string} options.filename    Base filename (date is appended).
 */
export const exportTablePdf = ({ title, subtitle, columns, rows, filename }) => {
  const doc = new jsPDF({ unit: 'pt', format: 'a4' });
  const marginX = 40;
  const cellPadding = 6;
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const usableWidth = pageWidth - marginX * 2;

  let y = 48;

  const ensureSpace = (needed) => {
    if (y + needed > pageHeight - 48) {
      doc.addPage();
      y = 48;
    }
  };

  // Font size scales down when the table has many columns so it always fits.
  const fontSize = columns.length > 16 ? 6.5 : columns.length > 12 ? 7 : 8;
  const lineHeight = fontSize + 2;
  const headerFontSize = Math.max(6.5, fontSize);
  const headerLineHeight = headerFontSize + 2;

  const columnWidths = () => {
    const lengths = columns.map((col) => {
      let maxLen = col.header.length;
      rows.forEach((row) => {
        const value = col.render ? col.render(row) : (row[col.key] ?? '');
        maxLen = Math.max(maxLen, String(value).length);
      });
      return Math.max(1, maxLen);
    });
    const total = lengths.reduce((a, b) => a + b, 0) || 1;
    const minWidth = Math.min(28, usableWidth / columns.length);
    const widths = lengths.map((l) => Math.max(minWidth, (l / total) * usableWidth));
    // Rescale so the widths always sum exactly to usableWidth (no overflow).
    const sum = widths.reduce((a, b) => a + b, 0);
    const scale = usableWidth / sum;
    let acc = 0;
    return widths.map((w, i) => {
      const scaled = w * scale;
      const ww = i === widths.length - 1 ? usableWidth - acc : scaled;
      acc += ww;
      return ww;
    });
  };

  const widths = columnWidths();

  const drawHeaderRow = () => {
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(headerFontSize);
    // Wrap header text so it fits narrow columns.
    const wrappedHeaders = columns.map((col, i) =>
      doc.splitTextToSize(col.header, widths[i] - cellPadding * 2)
    );
    const headerHeight = Math.max(20, Math.max(...wrappedHeaders.map((l) => l.length)) * headerLineHeight + cellPadding * 2);
    ensureSpace(headerHeight);

    let x = marginX;
    columns.forEach((col, i) => {
      // Re-apply fill color per cell: doc.text() writes `0 g` (black fill),
      // which otherwise leaks into the next cell's background.
      doc.setFillColor(240, 240, 240);
      doc.setDrawColor(220, 220, 220);
      doc.rect(x, y, widths[i], headerHeight, 'FD');
      doc.setTextColor(0);
      doc.text(wrappedHeaders[i], x + cellPadding, y + cellPadding + headerLineHeight);
      x += widths[i];
    });
    y += headerHeight;
  };

  const drawRow = (row, rowIndex) => {
    // Compute wrapped text for every cell first so we know the row height.
    const wrapped = columns.map((col, i) => {
      const value = col.render ? col.render(row, rowIndex) : (row[col.key] ?? '');
      return doc.splitTextToSize(String(value), widths[i] - cellPadding * 2);
    });
    const rowHeight = Math.max(18, Math.max(...wrapped.map((lines) => lines.length)) * lineHeight + cellPadding * 2);
    ensureSpace(rowHeight);

    doc.setFont('helvetica', 'normal');
    doc.setFontSize(fontSize);
    let x = marginX;
    wrapped.forEach((lines, i) => {
      if (rowIndex % 2 === 1) {
        doc.setFillColor(248, 248, 248);
        doc.rect(x, y, widths[i], rowHeight, 'F');
      }
      doc.setDrawColor(230, 230, 230);
      doc.rect(x, y, widths[i], rowHeight, 'S');
      doc.setTextColor(0);
      doc.text(lines, x + cellPadding, y + cellPadding + lineHeight);
      x += widths[i];
    });
    y += rowHeight;
  };

  // Header / title block
  const generatedAt = new Date().toLocaleString();
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(10);
  doc.text('Distribution Management System', marginX, y);
  y += 14;
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(16);
  doc.text(title, marginX, y);
  y += 18;
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(10);
  doc.text(`Generated: ${generatedAt}`, marginX, y);
  y += 16;
  if (subtitle) {
    doc.setFontSize(9);
    const lines = doc.splitTextToSize(subtitle, usableWidth);
    doc.text(lines, marginX, y);
    y += lines.length * lineHeight + 6;
  }
  y += 4;

  if (rows.length === 0) {
    doc.text('No data to display for the current filters.', marginX, y);
  } else {
    drawHeaderRow();
    rows.forEach((row, i) => drawRow(row, i));
  }

  const fileDate = new Date().toISOString().slice(0, 10);
  doc.save(`${filename}-${fileDate}.pdf`);
};
