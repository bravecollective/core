/* default dom id (particles-js) */
//particlesJS();

/* config dom id */
//particlesJS('dom-id');

/* config dom id (optional) + config particles params */
particlesJS('particles', {
  particles: {
    color: '#9bbed3',
    color_random: false,
    shape: 'circle', // "circle", "edge" or "triangle"
    opacity: {
      opacity: 0.3,
      anim: {
        enable: true,
        speed: 1,
        opacity_min: 0,
        sync: false
      }
    },
    size: 1,
    size_random: false,
    nb: 150,
    line_linked: {
      enable_auto: true,
      distance: 580,
      color: '#9bbed3',
      opacity: .23,
      width: 1,
      condensed_mode: {
        enable: true,
        rotateX: 600,
        rotateY: 900
      }
    },
    anim: {
      enable: true,
      speed: 2
    }
  },
  interactivity: {
    enable: false
  },
  /* Retina Display Support */
  retina_detect: true
});