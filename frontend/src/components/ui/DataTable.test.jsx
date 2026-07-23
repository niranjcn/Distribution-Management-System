import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import DataTable from './DataTable'

vi.mock('../../services/api', () => ({
  dashboardAPI: {
    trackActivity: vi.fn().mockResolvedValue({}),
  },
}))

const columns = [
  { key: 'name', label: 'Name' },
  { key: 'role', label: 'Role' },
  { key: 'status', label: 'Status' },
]

const data = [
  { id: '1', name: 'Alice', role: 'Admin', status: 'active' },
  { id: '2', name: 'Bob', role: 'User', status: 'inactive' },
  { id: '3', name: 'Charlie', role: 'Manager', status: 'active' },
  { id: '4', name: 'Diana', role: 'User', status: 'active' },
  { id: '5', name: 'Eve', role: 'Admin', status: 'inactive' },
]

describe('DataTable', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders column headers', () => {
    render(<DataTable columns={columns} data={data} />)
    expect(screen.getByText('Name')).toBeInTheDocument()
    expect(screen.getByText('Role')).toBeInTheDocument()
    expect(screen.getByText('Status')).toBeInTheDocument()
  })

  it('renders data rows in the table', () => {
    const { container } = render(<DataTable columns={columns} data={data} />)
    const tds = container.querySelectorAll('td')
    expect(tds[0].textContent).toBe('Alice')
    expect(tds[1].textContent).toBe('Admin')
  })

  it('shows empty state when no data', () => {
    render(<DataTable columns={columns} data={[]} />)
    const messages = screen.getAllByText('No data found')
    expect(messages.length).toBeGreaterThanOrEqual(1)
  })

  it('filters rows by search query', async () => {
    const user = userEvent.setup()
    const { container } = render(<DataTable columns={columns} data={data} />)

    const searchInput = screen.getByPlaceholderText('Search...')
    await user.type(searchInput, 'Alice')

    const tds = container.querySelectorAll('td')
    expect(tds[0].textContent).toBe('Alice')
  })

  it('sorts rows when clicking a column header', async () => {
    const user = userEvent.setup()
    const { container } = render(<DataTable columns={columns} data={data} />)

    const nameHeader = screen.getByText('Name')
    await user.click(nameHeader)

    const rows = container.querySelectorAll('tbody tr')
    expect(rows[0].textContent).toContain('Alice')
  })

  it('paginates data correctly', () => {
    const manyData = Array.from({ length: 25 }, (_, i) => ({
      id: String(i + 1),
      name: `User ${i + 1}`,
      role: 'User',
      status: 'active',
    }))

    const { container } = render(<DataTable columns={columns} data={manyData} pageSize={10} />)

    const rows = container.querySelectorAll('tbody tr')
    expect(rows.length).toBe(10)
    expect(rows[0].textContent).toContain('User 1')
    expect(rows[9].textContent).toContain('User 10')
  })

  it('navigates to next page on clicking next', async () => {
    const user = userEvent.setup()
    const manyData = Array.from({ length: 25 }, (_, i) => ({
      id: String(i + 1),
      name: `User ${i + 1}`,
      role: 'User',
      status: 'active',
    }))

    const { container } = render(<DataTable columns={columns} data={manyData} pageSize={10} />)

    const chevronRight = container.querySelector('.lucide-chevron-right')
    const nextBtn = chevronRight.closest('button')
    await user.click(nextBtn)

    const matches = container.querySelectorAll('td')
    const firstDataCell = matches[0]
    expect(firstDataCell.textContent).toContain('User 11')
  })

  it('renders custom cell content via render prop', () => {
    const cols = [
      { key: 'name', label: 'Name', render: (val) => `Mr. ${val}` },
    ]
    const { container } = render(<DataTable columns={cols} data={[{ id: '1', name: 'Alice' }]} />)
    const tds = container.querySelectorAll('td')
    expect(tds[0].textContent).toContain('Mr. Alice')
  })
})
