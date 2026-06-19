import fs from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputPath = fileURLToPath(
  new URL("../deliverables/档案迁移导入模板.xlsx", import.meta.url),
);
const outputDir = fileURLToPath(new URL("../deliverables/", import.meta.url));

const workbook = Workbook.create();
const input = workbook.worksheets.add("档案导入");
const guide = workbook.worksheets.add("填写说明");

input.getRange("A1:E1").values = [[
  "盒号",
  "文件名称",
  "载体类型",
  "份数描述",
  "电子文件路径",
]];
input.getRange("A1:E101").format.borders = {
  top: { style: "thin", color: "#D8DEE9" },
  bottom: { style: "thin", color: "#D8DEE9" },
  left: { style: "thin", color: "#D8DEE9" },
  right: { style: "thin", color: "#D8DEE9" },
  insideHorizontal: { style: "hair", color: "#E5E9F0" },
  insideVertical: { style: "hair", color: "#E5E9F0" },
};
input.getRange("A1:E1").format = {
  fill: "#1F4E78",
  font: { bold: true, color: "#FFFFFF", size: 11 },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
input.getRange("A2:E101").format = {
  fill: "#FFFFFF",
  font: { color: "#263238", size: 10 },
  verticalAlignment: "center",
};
input.getRange("A1:A101").format.columnWidth = 14;
input.getRange("B1:B101").format.columnWidth = 30;
input.getRange("C1:C101").format.columnWidth = 16;
input.getRange("D1:D101").format.columnWidth = 16;
input.getRange("E1:E101").format.columnWidth = 52;
input.getRange("A1:E1").format.rowHeight = 24;
input.freezePanes.freezeRows(1);
input.getRange("C2:C101").dataValidation = {
  rule: {
    type: "list",
    formula1: '"原件,复印件,电子件,其他"',
  },
};

guide.getRange("A1:B1").values = [["档案迁移导入模板填写说明", ""]];
guide.getRange("A1:B1").format = {
  fill: "#1F4E78",
  font: { bold: true, color: "#FFFFFF", size: 16 },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  rowHeight: 34,
};

guide.getRange("A3:B9").values = [
  ["项目", "说明"],
  ["导入范围", "一个 Excel 文件导入到当前选中的一个项目。"],
  ["文件名称", "必填；空白行不会成为有效档案。"],
  ["盒号", "可留空，例如 A-001。"],
  ["载体类型", "可从下拉列表选择，也可填写其他文字。"],
  ["份数描述", "允许填写 3份、2本 等文字。"],
  ["电子文件路径", "填写 Windows 绝对路径；系统只保存路径，不复制文件。"],
];
guide.getRange("A3:B3").format = {
  fill: "#5B9BD5",
  font: { bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
};
guide.getRange("A4:A9").format = {
  fill: "#D9EAF7",
  font: { bold: true, color: "#1F2937" },
};
guide.getRange("A3:B9").format.borders = {
  top: { style: "thin", color: "#B8C4CE" },
  bottom: { style: "thin", color: "#B8C4CE" },
  left: { style: "thin", color: "#B8C4CE" },
  right: { style: "thin", color: "#B8C4CE" },
  insideHorizontal: { style: "thin", color: "#D8DEE9" },
  insideVertical: { style: "thin", color: "#D8DEE9" },
};
guide.getRange("A3:A9").format.columnWidth = 18;
guide.getRange("B3:B9").format.columnWidth = 64;
guide.getRange("B4:B9").format.wrapText = true;
guide.getRange("A11:B11").values = [[
  "重要提示",
  "不要修改“档案导入”工作表的表头，不要增加标题行或合并数据单元格；重复导入会产生重复档案。",
]];
guide.getRange("A11:B11").format = {
  fill: "#FFF2CC",
  font: { bold: true, color: "#7F6000" },
  wrapText: true,
  rowHeight: 38,
};
guide.showGridlines = false;

await fs.mkdir(outputDir, { recursive: true });
const exported = await SpreadsheetFile.exportXlsx(workbook);
await exported.save(outputPath);

const tableCheck = await workbook.inspect({
  kind: "table",
  range: "档案导入!A1:E6",
  include: "values,formulas",
  tableMaxRows: 6,
  tableMaxCols: 5,
});
console.log(tableCheck.ndjson);

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 50 },
  summary: "formula error scan",
});
console.log(errors.ndjson);

const inputPreview = await workbook.render({
  sheetName: "档案导入",
  range: "A1:E12",
  scale: 1.5,
});
await fs.writeFile(
  fileURLToPath(new URL("../deliverables/template-preview.png", import.meta.url)),
  Buffer.from(await inputPreview.arrayBuffer()),
);

const guidePreview = await workbook.render({
  sheetName: "填写说明",
  range: "A1:B11",
  scale: 1.5,
});
await fs.writeFile(
  fileURLToPath(new URL("../deliverables/guide-preview.png", import.meta.url)),
  Buffer.from(await guidePreview.arrayBuffer()),
);
