import type { IconName } from '@/lib/icons'

export type NavId =
  | 'today'
  | 'calendar'
  | 'trades'
  | 'stats'
  | 'more'
  | 'diagnosis'
  | 'playbook'
  | 'alerts'
  | 'accounts'
  | 'settings'
  | 'mentor'
  | 'mentorQueue'
  | 'mentorAlerts'

export type BadgeSource = 'pendingTrades' | 'unreadAlerts' | 'mentorQueue'

export interface NavItem {
  id: NavId
  to: string
  labelKey: string
  icon: IconName
  badge?: { source: BadgeSource; tone: 'warning' | 'loss' }
}

export interface NavGroup {
  titleKey?: string
  items: NavItem[]
}

// Sidebar groups mirror screens/source/WSide.dc.html.
export const traderSideNav: NavGroup[] = [
  {
    items: [
      { id: 'today', to: '/', labelKey: 'nav.today', icon: 'today' },
      { id: 'calendar', to: '/calendar', labelKey: 'nav.calendar', icon: 'calendar' },
      {
        id: 'trades',
        to: '/trades',
        labelKey: 'nav.trades',
        icon: 'trades',
        badge: { source: 'pendingTrades', tone: 'warning' },
      },
      { id: 'stats', to: '/stats', labelKey: 'nav.stats', icon: 'performance' },
    ],
  },
  {
    titleKey: 'nav.groups.tools',
    items: [
      { id: 'diagnosis', to: '/diagnosis', labelKey: 'nav.diagnosis', icon: 'aiCoach' },
      { id: 'playbook', to: '/playbook', labelKey: 'nav.playbook', icon: 'playbook' },
      {
        id: 'alerts',
        to: '/alerts',
        labelKey: 'nav.alerts',
        icon: 'alerts',
        badge: { source: 'unreadAlerts', tone: 'loss' },
      },
    ],
  },
  {
    titleKey: 'nav.groups.account',
    items: [
      { id: 'accounts', to: '/accounts', labelKey: 'nav.accounts', icon: 'accounts' },
      { id: 'settings', to: '/settings', labelKey: 'nav.settings', icon: 'settings' },
    ],
  },
]

export const mentorSideNav: NavGroup[] = [
  {
    items: [
      { id: 'mentor', to: '/mentor', labelKey: 'nav.mentorTraders', icon: 'mentorGroup' },
      {
        id: 'mentorQueue',
        to: '/mentor/queue',
        labelKey: 'nav.mentorQueue',
        icon: 'review',
        badge: { source: 'mentorQueue', tone: 'warning' },
      },
      { id: 'mentorAlerts', to: '/alerts', labelKey: 'nav.mentorAlerts', icon: 'ruleBreach' },
    ],
  },
  {
    titleKey: 'nav.groups.account',
    items: [{ id: 'settings', to: '/settings', labelKey: 'nav.mentorSettings', icon: 'settings' }],
  },
]

// BottomNav: exactly five items (design-system/components/BottomNav.md).
export const bottomNav: NavItem[] = [
  { id: 'today', to: '/', labelKey: 'nav.today', icon: 'today' },
  { id: 'calendar', to: '/calendar', labelKey: 'nav.calendar', icon: 'calendar' },
  {
    id: 'trades',
    to: '/trades',
    labelKey: 'nav.trades',
    icon: 'trades',
    badge: { source: 'pendingTrades', tone: 'loss' },
  },
  { id: 'stats', to: '/stats', labelKey: 'nav.stats', icon: 'performance' },
  { id: 'more', to: '/more', labelKey: 'nav.more', icon: 'more' },
]

/** Destinations behind "More" on mobile = the sidebar's tools + account groups. */
export const moreNav: NavGroup[] = traderSideNav.slice(1)
