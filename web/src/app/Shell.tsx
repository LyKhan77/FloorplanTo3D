import { Content, Header, HeaderGlobalBar, HeaderName, SideNav, SideNavItems, SideNavLink, SkipToContent, Theme } from '@carbon/react'
import type { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { HealthIndicator } from '../components/HealthIndicator'

const NAV = [
  { to: '/projects', label: 'Projects' },
  { to: '/templates', label: 'Templates' },
  { to: '/system', label: 'System' },
]

export function Shell({ children }: { children: ReactNode }) {
  const { pathname } = useLocation()
  return (
    <Theme theme="g100" className="app-theme">
      <Header aria-label="Floorplan3D">
        <SkipToContent />
        <HeaderName as={Link} to="/projects" prefix="">Floorplan3D</HeaderName>
        <HeaderGlobalBar>
          <HealthIndicator />
        </HeaderGlobalBar>
        <SideNav aria-label="Navigasi" expanded isPersistent isFixedNav>
          <SideNavItems>
            {NAV.map((n) => (
              <SideNavLink key={n.to} as={Link} to={n.to} isActive={pathname.startsWith(n.to)}>{n.label}</SideNavLink>
            ))}
          </SideNavItems>
        </SideNav>
      </Header>
      <Content id="main-content" className="app-content">{children}</Content>
    </Theme>
  )
}
