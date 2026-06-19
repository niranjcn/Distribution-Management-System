import re

with open("frontend/src/pages/Reports.jsx", "r") as f:
    code = f.read()

# 1. Fix the useEffect to pass dateRange and only start_date
old_effect = """  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [devRes, invRes, distRes, defRes, retRes] = await Promise.all([
          devicesAPI.getDevices({ page: 1, page_size: 100 }).catch(() => ({ data: [] })),
          reportsAPI.getInventoryReport().catch(() => ({ data: null })),
          reportsAPI.getDistributionSummary().catch(() => ({ data: null })),
          reportsAPI.getDefectSummary().catch(() => ({ data: null })),
          reportsAPI.getReturnSummary().catch(() => ({ data: null }))
        ]);"""
new_effect = """  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const start = buildRangeStart(dateRange);
        const params = {};
        if (start && dateRange !== 'all') {
          params.start_date = start.toISOString();
        }

        const [devRes, invRes, distRes, defRes, retRes] = await Promise.all([
          devicesAPI.getDevices({ page: 1, page_size: 100, ...params }).catch(() => ({ data: [] })),
          reportsAPI.getInventoryReport(params).catch(() => ({ data: null })),
          reportsAPI.getDistributionSummary(params).catch(() => ({ data: null })),
          reportsAPI.getDefectSummary(params).catch(() => ({ data: null })),
          reportsAPI.getReturnSummary(params).catch(() => ({ data: null }))
        ]);"""
code = code.replace(old_effect, new_effect)
code = code.replace("}, []);", "}, [dateRange]);")

# 2. Remove tabs from reportTypes
old_tabs = """  const reportTypes = [
    { id: 'overview', label: 'Overview', icon: BarChart3 },
    { id: 'devices', label: 'Device Reports', icon: Box },
    { id: 'distributions', label: 'Distribution Reports', icon: Package },
    { id: 'defects', label: 'Defect Reports', icon: AlertTriangle },
    { id: 'returns', label: 'Return Reports', icon: RotateCcw },
    { id: 'account_changes', label: 'Request Account Changes', icon: UserCog },
  ];"""
new_tabs = """  const reportTypes = [
    { id: 'overview', label: 'Overview', icon: BarChart3 },
    { id: 'account_changes', label: 'Request Account Changes', icon: UserCog },
  ];"""
code = code.replace(old_tabs, new_tabs)

# 3. Simplify the reportType blocks
# We'll use regex to remove the devices, distributions, defects, and returns blocks entirely.
# They are wrapped as {reportType === 'devices' && ( <Card title="..."> ... </Card> )}
code = re.sub(r"\{reportType === 'devices' && \([\s\S]*?</Card>\n\s*\)\}", "", code)
code = re.sub(r"\{reportType === 'distributions' && \([\s\S]*?</Card>\n\s*\)\}", "", code)
code = re.sub(r"\{reportType === 'defects' && \([\s\S]*?</Card>\n\s*\)\}", "", code)
code = re.sub(r"\{reportType === 'returns' && \([\s\S]*?</Card>\n\s*\)\}", "", code)

# 4. Remove all other reportType conditionals that check for overview or devices,
# since the entire rest of the page (Overview Stats -> Summary Table) should just be inside one block.
# Specifically, we want:
# {reportType === 'overview' && ( <div className="space-y-6"> [all overview content] </div> )}
# We will do this by stripping out the existing conditionals:
code = code.replace("{reportType === 'overview' && (", "")
code = code.replace("{(reportType === 'overview' || reportType === 'devices') && (", "")
code = code.replace("{reportType !== 'account_changes' && (", "")
# Strip the specific closing braces that matched those:
# There are three matching `)}` that we need to remove.
# Let's find them manually:
code = code.replace("      </div>\n      )}\n\n      <div className=\"grid grid-cols-1 lg:grid-cols-2 gap-6\">", "      </div>\n\n      <div className=\"grid grid-cols-1 lg:grid-cols-2 gap-6\">")
code = code.replace("      </div>\n      )}\n\n      <div className=\"grid grid-cols-1 gap-6 my-6\">", "      </div>\n\n      <div className=\"grid grid-cols-1 gap-6 my-6\">")
code = code.replace("        </Card>\n      </div>\n      )}\n\n      {/* Summary Table */}", "        </Card>\n      </div>\n\n      {/* Summary Table */}")

# Finally wrap the overview content.
# The overview content starts at {/* Overview Stats */}
# and ends at the end of the file.
old_overview_start = "      {/* Overview Stats */}\n      \n      <div className=\"grid grid-cols-2 md:grid-cols-4 gap-4\">"
new_overview_start = "      {/* Overview Stats */}\n      {reportType === 'overview' && (\n        <div className=\"space-y-6\">\n          <div className=\"grid grid-cols-2 md:grid-cols-4 gap-4\">"
code = code.replace(old_overview_start, new_overview_start)

# Add closing brace at the end of the file
code = code.replace("    </div>\n  );\n};\n\nexport default Reports;", "        </div>\n      )}\n    </div>\n  );\n};\n\nexport default Reports;")

with open("frontend/src/pages/Reports.jsx", "w") as f:
    f.write(code)

print("Fix applied successfully.")
