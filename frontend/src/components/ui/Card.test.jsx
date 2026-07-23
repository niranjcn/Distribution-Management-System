import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { Cpu } from 'lucide-react'
import Card from './Card'

describe('Card', () => {
  it('renders children', () => {
    render(<Card><p>content</p></Card>)
    expect(screen.getByText('content')).toBeInTheDocument()
  })

  it('renders title when provided', () => {
    render(<Card title="My Card">child</Card>)
    expect(screen.getByText('My Card')).toBeInTheDocument()
  })

  it('renders subtitle when provided', () => {
    render(<Card title="Title" subtitle="Sub">child</Card>)
    expect(screen.getByText('Sub')).toBeInTheDocument()
  })

  it('renders icon when provided', () => {
    const { container } = render(<Card title="Card" icon={Cpu}>child</Card>)
    const icon = container.querySelector('.lucide-cpu')
    expect(icon).toBeInTheDocument()
  })

  it('renders action element when provided', () => {
    render(<Card title="Card" action={<button>Action</button>}>child</Card>)
    expect(screen.getByRole('button', { name: 'Action' })).toBeInTheDocument()
  })

  it('does not render header when title and action are missing', () => {
    const { container } = render(<Card>child</Card>)
    const header = container.querySelector('.border-b')
    expect(header).not.toBeInTheDocument()
  })

  it('applies padding class by default', () => {
    const { container } = render(<Card>child</Card>)
    const content = container.querySelector('.p-4')
    expect(content).toBeInTheDocument()
  })

  it('removes padding when padding is false', () => {
    const { container } = render(<Card padding={false}>child</Card>)
    const padded = container.querySelector('.p-4')
    expect(padded).not.toBeInTheDocument()
  })

  it('applies custom className', () => {
    const { container } = render(<Card className="custom-class">child</Card>)
    const card = container.firstChild
    expect(card.className).toContain('custom-class')
  })
})
