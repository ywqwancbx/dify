import React from 'react'
import Link from 'next/link'
import { RiDiscordFill, RiGithubFill } from '@remixicon/react'
import { useTranslation } from 'react-i18next'

type CustomLinkProps = {
  href: string
  children: React.ReactNode
}

const CustomLink = React.memo(({
  href,
  children,
}: CustomLinkProps) => {
  return (
    <Link
      className='flex h-8 w-8 cursor-pointer items-center justify-center transition-opacity duration-200 ease-in-out hover:opacity-80'
      target='_blank'
      rel='noopener noreferrer'
      href={href}
    >
      {children}
    </Link>
  )
})

const Footer = () => {
  // Community footer removed
  return null
}

export default React.memo(Footer)
