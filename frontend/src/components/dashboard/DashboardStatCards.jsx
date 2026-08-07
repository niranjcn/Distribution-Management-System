import { Activity, CheckSquare, ShieldCheck } from 'lucide-react'
import StatCard from '../ui/StatCard'

const periodLabel = (range) => ({
  all: 'all time',
  today: 'today',
  last7: 'last 7 days',
  last30: 'last 30 days',
  last90: 'last 90 days',
  thisYear: 'this year',
  custom: 'selected period',
}[range] || 'selected period')

const DashboardStatCards = ({ stats, kpis, reliabilitySummary, dateRange, loading = false, statsLoading, advancedLoading }) => {
  // Batch granular loading: rows 1-2 come from /dashboard/stats (fast), rows
  // 3-4 from /dashboard/advanced-metrics (slower). Each group shows skeletons
  // only until its own request resolves so the top cards populate first.
  const loadingStats = statsLoading ?? loading;
  const loadingAdvanced = advancedLoading ?? loading;

  return (
    <>
      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3 sm:gap-4 animate-slideUp">
        <StatCard title="Total Devices" value={stats.total_devices ?? 0} description="All registered devices" color="total" loading={loadingStats} />
        <StatCard title="Total Active Devices" value={stats.total_active_devices ?? 0} description="Currently active" color="online" loading={loadingStats} />
        <StatCard title="Total Distributed Devices" value={stats.total_distributed_devices ?? 0} description="Currently distributed" color="teal" loading={loadingStats} />
        <StatCard title="Total Inactive Devices" value={stats.total_inactive_devices ?? 0} description="Currently inactive" color="offline" loading={loadingStats} />
        <StatCard title="Total Defective Devices" value={stats.total_defective_devices ?? 0} description="Currently defective" color="red" loading={loadingStats} />
        <StatCard title="Total Replaced Devices" value={stats.total_replaced_devices ?? 0} description="Ever replaced" color="purple" loading={loadingStats} />
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 sm:gap-4 animate-slideUp">
        <StatCard title="Registered in Period" value={stats.registered_in_range ?? 0} description={`Devices created in ${periodLabel(dateRange.range)}`} color="total" loading={loadingStats} />
        <StatCard title="Distributed in Period" value={stats.distributed_in_range ?? 0} description={`Devices distributed in ${periodLabel(dateRange.range)}`} color="blue" loading={loadingStats} />
        <StatCard title="Inactive in Period" value={stats.inactive_in_range ?? 0} description={`Became inactive in ${periodLabel(dateRange.range)}`} color="offline" loading={loadingStats} />
        <StatCard title="Defective in Period" value={stats.defective_in_range ?? 0} description={`Became defective in ${periodLabel(dateRange.range)}`} color="red" loading={loadingStats} />
        <StatCard title="Replacements in Period" value={stats.replacements_in_range ?? 0} description={`Replaced in ${periodLabel(dateRange.range)}`} color="purple" loading={loadingStats} />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4 animate-slideUp">
        <StatCard title="Defect Incidence" value={`${reliabilitySummary.defect_incidence_percentage ?? 0}%`} icon={Activity} color="red" description={`Defects in ${periodLabel(dateRange.range)}`} loading={loadingAdvanced} />
        <StatCard title="Repaired in 60 Days" value={reliabilitySummary.repaired_within_sla_devices ?? 0} icon={CheckSquare} color="green" description={`Resolved within 60 days in ${periodLabel(dateRange.range)}`} loading={loadingAdvanced} />
        <StatCard title="60-Day Repair Rate" value={`${reliabilitySummary.repaired_within_sla_percentage ?? 0}%`} icon={ShieldCheck} color="indigo" description={`Of resolved defects in ${periodLabel(dateRange.range)}`} loading={loadingAdvanced} />
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 animate-slideUp">
        <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm"><p className="text-xs text-gray-400 uppercase tracking-wide">Operators</p><p className="text-xl font-bold text-gray-800 mt-1">{kpis.total_operators ?? 0}</p></div>
        <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm"><p className="text-xs text-gray-400 uppercase tracking-wide">Sub Distributors</p><p className="text-xl font-bold text-gray-800 mt-1">{kpis.total_sub_distributors ?? 0}</p></div>
        <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm"><p className="text-xs text-gray-400 uppercase tracking-wide">Clusters</p><p className="text-xl font-bold text-gray-800 mt-1">{kpis.total_clusters ?? 0}</p></div>
        <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm"><p className="text-xs text-gray-400 uppercase tracking-wide">Staff</p><p className="text-xl font-bold text-gray-800 mt-1">{kpis.total_staff ?? 0}</p></div>
      </div>
    </>
  )
}

export default DashboardStatCards
