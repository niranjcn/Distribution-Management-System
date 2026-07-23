import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { Cpu } from 'lucide-react'
import StatCard from './StatCard'

describe('StatCard', () => {
  it('renders title and value', () => {
    render(<StatCard title="Total Devices" value={42} />)
    expect(screen.getByText('Total Devices')).toBeInTheDocument()
    expect(screen.getByText('42')).toBeInTheDocument()
  })

  it('renders description when provided', () => {
    render(<StatCard title="Active" value={10} description="Currently active devices" />)
    expect(screen.getByText('Currently active devices')).toBeInTheDocument()
  })

  it('renders icon when provided', () => {
    const { container } = render(<StatCard title="Devices" value={5} icon={Cpu} />)
    const icon = container.querySelector('.lucide-cpu')
    expect(icon).toBeInTheDocument()
  })

  it('applies the correct color variant', () => {
    const { container } = render(<StatCard title="Defective" value={3} color="red" />)
    const card = container.querySelector('.stat-card')
    expect(card.className).toContain('border-l-red-500')
  })

  it('defaults to blue color when no color is given', () => {
    const { container } = render(<StatCard title="Test" value={0} />)
    const card = container.querySelector('.stat-card')
    expect(card.className).toContain('border-l-blue-500')
  })

  it('renders skeleton elements when loading', () => {
    const { container } = render(<StatCard title="Devices" value={99} loading />)
    expect(container.querySelector('.animate-pulse')).toBeInTheDocument()
    expect(screen.queryByText('99')).not.toBeInTheDocument()
  })

  it('does not show skeleton when loading is false', () => {
    const { container } = render(<StatCard title="Devices" value={99} />)
    expect(container.querySelector('.animate-pulse')).not.toBeInTheDocument()
    expect(screen.getByText('99')).toBeInTheDocument()
  })
})
