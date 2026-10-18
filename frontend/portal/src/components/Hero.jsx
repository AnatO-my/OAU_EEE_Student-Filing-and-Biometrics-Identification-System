import { motion } from "framer-motion";
import { Carousel } from "react-responsive-carousel";
import "react-responsive-carousel/lib/styles/carousel.min.css"; // Import default styles
import { Link } from "react-router-dom";
const Hero = () => {
  const images = [
    "./src/assets/fast1193.webp",
    "./src/assets/oau.jpg",
    "./src/assets/OIP (1).webp",
  ];

  return (
    <div className="relative h-[70svh] min-h-[26rem] max-h-[40rem] overflow-hidden">
      <Carousel
        className="absolute inset-0 -z-10"
        showThumbs={false} // Hide thumbnail previews
        infiniteLoop={true} // Loop slides
        autoPlay={true} // Auto play slides
        interval={3000} // Time between slides (ms)
        stopOnHover={true} // Pause on hover
        showStatus={false} // Hide status text
        swipeable={true} // Enable swipe gestures
        emulateTouch={true} // Enable touch on desktop
      >
        {images.map((src, index) => (
          <div key={index} className="h-full min-h-[26rem]">
            <img
              className="h-full w-full object-cover"
              src={src}
              alt={`Slide ${index + 1}`}
            />
          </div>
        ))}
      </Carousel>

      <div className="absolute inset-0 bg-black/50" />

      <motion.div
        className="relative z-10 flex h-full flex-col items-center justify-center px-6 text-center text-white"
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, ease: "easeOut" }}
      >
        <motion.h1
          className="text-3xl font-bold sm:text-4xl md:text-6xl"
          initial={{ opacity: 0, x: -40 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2, duration: 0.8 }}
        >
          EEE OAU Filing System
        </motion.h1>

        <motion.p
          className="mt-4 max-w-2xl text-base sm:text-lg md:text-xl"
          initial={{ opacity: 0, x: 40 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.4, duration: 0.8 }}
        >
          Streamline your filing process with speed and confidence.
        </motion.p>

        <motion.div
          className="mt-8 flex w-full flex-wrap items-center justify-center gap-3 sm:gap-4"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6, duration: 0.8 }}
        >
          <Link
            to="/register"
            className="rounded-full bg-blue-600 px-6 py-3 font-semibold text-white shadow-lg transition duration-200 hover:bg-blue-500"
          >
            Register
          </Link>
          <Link
            to="/login"
            className="rounded-full border border-white/60 bg-white/10 px-6 py-3 font-semibold text-white backdrop-blur-sm transition duration-200 hover:bg-white/20"
          >
            Login
          </Link>
          <Link
            to="/student/profile"
            className="rounded-full border border-white/60 bg-transparent px-6 py-3 font-semibold text-white transition duration-200 hover:bg-white/10"
          >
            My Profile
          </Link>
        </motion.div>
      </motion.div>
    </div>
  );
};

export default Hero;
