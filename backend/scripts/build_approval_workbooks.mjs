import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = path.resolve("demo_documents", "approval_pack");
const manifestPath = path.join(root, ".workbook_manifest.json");
const manifest = JSON.parse(await fs.readFile(manifestPath, "utf8"));
const previewRoot = path.resolve("tmp", "approval_pack_workbooks");
await fs.mkdir(previewRoot, { recursive: true });

for (const item of manifest) {
  const workbook = Workbook.create();
  const sheet = workbook.worksheets.add("Evidence");
  const rows = item.rows;
  const data = [["Field", "Value"], ...rows];
  sheet.getRange("A1:C1").merge();
  sheet.getRange("A1").values = [[item.title]];
  sheet.getRange(`A3:B${data.length + 2}`).values = data;
  sheet.getRange("A1:C1").format = {
    fill: "#211B3B",
    font: { color: "#F5F1E6", bold: true, size: 16 },
    horizontalAlignment: "center",
    verticalAlignment: "center",
  };
  sheet.getRange("A3:B3").format = {
    fill: "#EED593",
    font: { color: "#211B3B", bold: true },
  };
  sheet.getRange(`A3:B${data.length + 2}`).format.borders = {
    preset: "inside",
    style: "thin",
    color: "#D9D9D9",
  };
  sheet.getRange(`A4:A${data.length + 2}`).format.font = { bold: true, color: "#211B3B" };
  sheet.getRange(`A3:B${data.length + 2}`).format.wrapText = true;
  sheet.getRange("A:A").format.columnWidth = 30;
  sheet.getRange("B:B").format.columnWidth = 48;
  sheet.getRange("C:C").format.columnWidth = 4;
  sheet.getRange("A1:C1").format.rowHeight = 28;
  sheet.freezePanes.freezeRows(3);
  sheet.showGridLines = false;

  const outputPath = path.resolve(item.path);
  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(outputPath);

  const inspection = await workbook.inspect({
    kind: "workbook,sheet,region",
    sheetId: "Evidence",
    range: `A1:B${data.length + 2}`,
    maxChars: 2500,
    tableMaxRows: 12,
    tableMaxCols: 3,
  });
  console.log(JSON.stringify({ file: outputPath, inspection }));

  const preview = await workbook.render({ sheetName: "Evidence", autoCrop: "all", scale: 1, format: "png" });
  const previewPath = path.join(previewRoot, `${path.basename(outputPath, ".xlsx")}.png`);
  await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
  console.log(JSON.stringify({ preview: previewPath }));
}

await fs.unlink(manifestPath);
