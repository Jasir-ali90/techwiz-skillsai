import logo from '../assets/brand/logo.png'
import logoDark from '../assets/brand/logo-dark.png'

type Props = {
  height?: number
  /** 'auto' follows the theme; 'dark' is for panels that are dark in every theme. */
  surface?: 'auto' | 'dark'
}

/** The SkillSprint mark and wordmark. Regenerate the images with scripts/build_brand_assets.py. */
export function Logo({ height = 32, surface = 'auto' }: Props) {
  if (surface === 'dark') {
    return (
      <span className="logo" style={{ height }}>
        <img src={logoDark} alt="SkillSprint" />
      </span>
    )
  }
  return (
    <span className="logo" style={{ height }}>
      <img className="logo-on-light" src={logo} alt="SkillSprint" />
      <img className="logo-on-dark" src={logoDark} alt="SkillSprint" />
    </span>
  )
}
