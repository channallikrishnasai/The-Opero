import { useState, type ReactNode } from "react";
import { motion, type Variants } from "motion/react";
import { Circle, Chrome, Github, Eye } from "lucide-react";

const heroContainer: Variants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.15, delayChildren: 0.2 },
  },
};

const heroChild: Variants = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5 } },
};

export default function App() {
  const [showPassword, setShowPassword] = useState(false);

  return (
    <main className="flex min-h-screen w-full bg-black selection:bg-white/30 p-2 transition-all duration-500 lg:h-screen lg:overflow-hidden lg:p-4">
      <div className="relative hidden lg:flex w-[52%] flex-col items-center justify-end pb-32 px-12 rounded-3xl overflow-hidden shadow-2xl h-full">
        <video
          className="absolute inset-0 w-full h-full object-cover"
          autoPlay
          muted
          loop
          playsInline
        >
          <source
            src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260506_081238_406ed0e3-5d83-436e-a512-0bbff7ec5b95.mp4"
            type="video/mp4"
          />
        </video>

        <motion.div
          className="z-10 w-full max-w-xs space-y-8"
          variants={heroContainer}
          initial="hidden"
          animate="show"
        >
          <motion.div
            className="flex items-center gap-2"
            variants={heroChild}
          >
            <Circle className="fill-white text-white" size={20} />
            <span className="text-xl font-semibold tracking-tight">Aurora</span>
          </motion.div>

          <motion.div className="space-y-3" variants={heroChild}>
            <h1 className="text-4xl font-medium tracking-tight whitespace-nowrap">
              Join Aurora
            </h1>
            <p className="text-white/60 text-sm leading-relaxed px-4">
              Follow these 3 quick phases to activate your space.
            </p>
          </motion.div>

          <motion.div className="space-y-3" variants={heroChild}>
            <StepItem number={1} text="Register your identity" active />
            <StepItem number={2} text="Configure your studio" />
            <StepItem number={3} text="Finalize your profile" />
          </motion.div>
        </motion.div>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center py-12 lg:py-6 px-4 sm:px-12 lg:px-16 xl:px-24 overflow-y-auto lg:overflow-hidden">
        <motion.div
          className="w-full max-w-xl space-y-8 lg:space-y-6 sm:space-y-10"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        >
          <div className="space-y-2">
            <h2 className="text-3xl font-medium tracking-tight">
              Create New Profile
            </h2>
            <p className="text-white/40 text-sm">
              Input your basic details to begin the journey.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <SocialButton icon={<Chrome size={18} />} label="Google" />
            <SocialButton icon={<Github size={18} />} label="Github" />
          </div>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t border-white/10" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-black px-4 text-xs font-medium text-white/40 uppercase tracking-widest">
                Or
              </span>
            </div>
          </div>

          <form className="space-y-4" onSubmit={(e) => e.preventDefault()}>
            <div className="grid grid-cols-2 gap-4">
              <InputGroup label="First Name" placeholder="John" type="text" />
              <InputGroup label="Last Name" placeholder="Doe" type="text" />
            </div>

            <InputGroup
              label="Email"
              placeholder="name@example.com"
              type="email"
            />

            <div className="space-y-2">
              <div className="relative">
                <InputGroup
                  label="Password"
                  placeholder="••••••••"
                  type={showPassword ? "text" : "password"}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  aria-pressed={showPassword}
                  className="absolute right-4 top-[41px] text-white/40 hover:text-white/70 transition-colors"
                >
                  <Eye size={18} />
                </button>
              </div>
              <p className="text-white/30 text-xs">
                Requires at least 8 symbols.
              </p>
            </div>

            <button
              type="submit"
              className="w-full h-14 bg-white text-black font-semibold rounded-xl hover:bg-white/90 active:scale-[0.98] mt-4 transition-all"
            >
              Create Account
            </button>
          </form>

          <p className="text-center text-sm text-white/40">
            Member of the team?{" "}
            <a href="#" className="text-white hover:underline">
              Log in
            </a>
          </p>
        </motion.div>
      </div>
    </main>
  );
}

function StepItem({
  number,
  text,
  active = false,
}: {
  number: number;
  text: string;
  active?: boolean;
}) {
  return (
    <div
      className={`flex items-center gap-3 rounded-xl px-4 py-3 transition-colors ${
        active
          ? "bg-white text-black border border-white"
          : "bg-brand-gray text-white border-none"
      }`}
    >
      <span
        className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
          active ? "bg-black text-white" : "bg-white/10 text-white/40"
        }`}
      >
        {number}
      </span>
      <span className="text-sm font-medium">{text}</span>
    </div>
  );
}

function SocialButton({ icon, label }: { icon: ReactNode; label: string }) {
  return (
    <button
      type="button"
      className="flex h-12 w-full items-center justify-center gap-2 bg-black border border-white/10 rounded-xl hover:bg-white/5 transition-colors text-sm font-medium"
    >
      {icon}
      {label}
    </button>
  );
}

function InputGroup({
  label,
  placeholder,
  type,
}: {
  label: string;
  placeholder: string;
  type: string;
}) {
  const id = label.toLowerCase().replace(/\s+/g, "-");
  return (
    <div className="space-y-2">
      <label htmlFor={id} className="text-sm font-medium text-white">
        {label}
      </label>
      <input
        id={id}
        name={id}
        type={type}
        placeholder={placeholder}
        autoComplete={
          type === "password"
            ? "new-password"
            : label === "Email"
              ? "email"
              : label === "First Name"
                ? "given-name"
                : label === "Last Name"
                  ? "family-name"
                  : "on"
        }
        className="w-full bg-brand-gray border-none rounded-xl h-11 px-4 text-white placeholder:text-white/20 focus:ring-2 focus:ring-white/20 outline-none"
      />
    </div>
  );
}
