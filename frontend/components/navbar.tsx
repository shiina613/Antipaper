'use client'
import { AnimatedThemeToggler } from '@/components/ui/animated-theme-toggler'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { Menu, X } from 'lucide-react'
import Link from 'next/link'
import React from 'react'

const menuItems = [
    { name: 'Dashboard', href: '#dashboard' },
    { name: 'Tóm tắt', href: '#summary' },
    { name: 'Thuật ngữ', href: '#terms' },
    { name: 'Câu hỏi', href: '#questions' },
    { name: 'Q&A', href: '#qa' },
]

export const Navbar = () => {
    const [menuState, setMenuState] = React.useState(false)
    const [isScrolled, setIsScrolled] = React.useState(false)

    React.useEffect(() => {
        const handleScroll = () => {
            setIsScrolled(window.scrollY > 50)
        }
        window.addEventListener('scroll', handleScroll)
        return () => window.removeEventListener('scroll', handleScroll)
    }, [])
    return (
        <nav
            data-state={menuState && 'active'}
            className="fixed z-20 w-full px-2">
            <div className={cn('mx-auto mt-2 max-w-6xl px-6 transition-all duration-300 lg:px-12', isScrolled && 'bg-background/50 max-w-4xl rounded-full border backdrop-blur-lg lg:px-6')}>
                <div className="relative flex flex-wrap items-center justify-between gap-6 py-2 lg:gap-0 lg:py-2.5">
                    <div className="flex w-full justify-between lg:w-auto">
                        <Link
                            href="/"
                            aria-label="home"
                            className="flex items-center space-x-2">
                            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary dark:bg-primary/30">
                                <svg
                                    className="h-6 w-6 text-white"
                                    viewBox="0 0 24 24"
                                    fill="none"
                                    stroke="currentColor"
                                    strokeWidth="2.5"
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                >
                                    <path d="M4 5h10a4 4 0 0 1 4 4v10H8a4 4 0 0 1-4-4V5z" />
                                    <path d="M8 9h6" />
                                    <path d="M8 13h8" />
                                </svg>

                            </div>
                            <span className="text-lg font-semibold text-gray-900 dark:text-white">
                                Paperless Meetings
                            </span>
                        </Link>

                        <button
                            onClick={() => setMenuState(!menuState)}
                            aria-label={menuState == true ? 'Close Menu' : 'Open Menu'}
                            className="relative z-20 -m-2.5 -mr-4 block cursor-pointer p-2.5 lg:hidden">
                            <Menu className="in-data-[state=active]:rotate-180 in-data-[state=active]:scale-0 in-data-[state=active]:opacity-0 m-auto size-6 duration-200" />
                            <X className="in-data-[state=active]:rotate-0 in-data-[state=active]:scale-100 in-data-[state=active]:opacity-100 absolute inset-0 m-auto size-6 -rotate-180 scale-0 opacity-0 duration-200" />
                        </button>
                    </div>

                    <div className="absolute inset-0 m-auto hidden size-fit lg:block">
                        <ul className="flex gap-8 text-sm">
                            {menuItems.map((item, index) => (
                                <li key={index}>
                                    <Link
                                        href={item.href}
                                        className="text-muted-foreground hover:text-accent-foreground text-base block duration-150">
                                        <span>{item.name}</span>
                                    </Link>
                                </li>
                            ))}
                        </ul>
                    </div>

                    <div className="bg-background in-data-[state=active]:block lg:in-data-[state=active]:flex mb-6 hidden w-full flex-wrap items-center justify-end space-y-8 rounded-3xl border p-6 shadow-2xl shadow-zinc-300/20 md:flex-nowrap lg:m-0 lg:flex lg:w-fit lg:gap-6 lg:space-y-0 lg:border-transparent lg:bg-transparent lg:p-0 lg:shadow-none dark:shadow-none dark:lg:bg-transparent">
                        <div className="lg:hidden">
                            <ul className="space-y-6 text-base">
                                {menuItems.map((item, index) => (
                                    <li key={index}>
                                        <Link
                                            href={item.href}
                                            className="text-muted-foreground hover:text-accent-foreground block duration-150">
                                            <span>{item.name}</span>
                                        </Link>
                                    </li>
                                ))}
                            </ul>
                        </div>
                        <div className="flex w-full flex-col space-y-3 sm:flex-row sm:gap-3 sm:space-y-0 md:w-fit">
                            <AnimatedThemeToggler />
                            <Button
                                size="sm"
                                className={'lg:inline-flex rounded-full h-8 px-3 text-sm'} render={<Link href='#dashboard' />} nativeButton={false}>
                                <span>Mở dashboard</span>
                            </Button>
                        </div>
                    </div>
                </div>
            </div>
        </nav>
    )
}