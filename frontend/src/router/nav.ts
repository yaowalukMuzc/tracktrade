import {
  AiMagicIcon,
  Alert02Icon,
  Analytics01Icon,
  Book02Icon,
  Calendar03Icon,
  ChartCandlestickIcon,
  Home01Icon,
  Menu01Icon,
  NoteEditIcon,
  Notification01Icon,
  Settings02Icon,
  UserGroupIcon,
  Wallet01Icon,
} from '@hugeicons/core-free-icons'

export type Icon = typeof Home01Icon

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
  icon: Icon
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
      { id: 'today', to: '/', labelKey: 'nav.today', icon: Home01Icon },
      { id: 'calendar', to: '/calendar', labelKey: 'nav.calendar', icon: Calendar03Icon },
      {
        id: 'trades',
        to: '/trades',
        labelKey: 'nav.trades',
        icon: ChartCandlestickIcon,
        badge: { source: 'pendingTrades', tone: 'warning' },
      },
      { id: 'stats', to: '/stats', labelKey: 'nav.stats', icon: Analytics01Icon },
    ],
  },
  {
    titleKey: 'nav.groups.tools',
    items: [
      { id: 'diagnosis', to: '/diagnosis', labelKey: 'nav.diagnosis', icon: AiMagicIcon },
      { id: 'playbook', to: '/playbook', labelKey: 'nav.playbook', icon: Book02Icon },
      {
        id: 'alerts',
        to: '/alerts',
        labelKey: 'nav.alerts',
        icon: Notification01Icon,
        badge: { source: 'unreadAlerts', tone: 'loss' },
      },
    ],
  },
  {
    titleKey: 'nav.groups.account',
    items: [
      { id: 'accounts', to: '/accounts', labelKey: 'nav.accounts', icon: Wallet01Icon },
      { id: 'settings', to: '/settings', labelKey: 'nav.settings', icon: Settings02Icon },
    ],
  },
]

export const mentorSideNav: NavGroup[] = [
  {
    items: [
      { id: 'mentor', to: '/mentor', labelKey: 'nav.mentorTraders', icon: UserGroupIcon },
      {
        id: 'mentorQueue',
        to: '/mentor/queue',
        labelKey: 'nav.mentorQueue',
        icon: NoteEditIcon,
        badge: { source: 'mentorQueue', tone: 'warning' },
      },
      { id: 'mentorAlerts', to: '/alerts', labelKey: 'nav.mentorAlerts', icon: Alert02Icon },
    ],
  },
  {
    titleKey: 'nav.groups.account',
    items: [{ id: 'settings', to: '/settings', labelKey: 'nav.mentorSettings', icon: Settings02Icon }],
  },
]

// BottomNav: exactly five items (design-system/components/BottomNav.md).
export const bottomNav: NavItem[] = [
  { id: 'today', to: '/', labelKey: 'nav.today', icon: Home01Icon },
  { id: 'calendar', to: '/calendar', labelKey: 'nav.calendar', icon: Calendar03Icon },
  {
    id: 'trades',
    to: '/trades',
    labelKey: 'nav.trades',
    icon: ChartCandlestickIcon,
    badge: { source: 'pendingTrades', tone: 'loss' },
  },
  { id: 'stats', to: '/stats', labelKey: 'nav.stats', icon: Analytics01Icon },
  { id: 'more', to: '/more', labelKey: 'nav.more', icon: Menu01Icon },
]

/** Destinations behind "More" on mobile = the sidebar's tools + account groups. */
export const moreNav: NavGroup[] = traderSideNav.slice(1)
