import { motion, AnimatePresence } from "framer-motion";
import { Check, AlertCircle } from "lucide-react";

export type VoiceState =
  | "hidden"
  | "recording"
  | "transcribing"
  | "inserted"
  | "error";

export function VoiceOverlay({ state }: { state: VoiceState }) {
  return (
    <AnimatePresence>
      {state !== "hidden" && (
        <motion.div
          key="overlay"
          initial={{ opacity: 0, scale: 0.92, filter: "blur(8px)" }}
          animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
          exit={{ opacity: 0, scale: 0.94, filter: "blur(6px)" }}
          transition={{
            type: "spring",
            stiffness: 260,
            damping: 28,
            mass: 0.8,
          }}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: 140,
            height: 56,
            borderRadius: 28,
            position: "relative",
            // Liquid glass container
            background:
              "linear-gradient(135deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.03) 50%, rgba(255,255,255,0.06) 100%)",
            backdropFilter: "blur(40px) saturate(1.4)",
            WebkitBackdropFilter: "blur(40px) saturate(1.4)",
            border: "1px solid rgba(255,255,255,0.12)",
            boxShadow: [
              "0 24px 48px rgba(0,0,0,0.24)",
              "0 8px 24px rgba(0,0,0,0.12)",
              "inset 0 1px 0 rgba(255,255,255,0.1)",
              "inset 0 -1px 0 rgba(255,255,255,0.03)",
            ].join(", "),
          }}
        >
          {/* Inner atmospheric bloom */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              borderRadius: 28,
              background:
                "radial-gradient(ellipse at 50% 50%, rgba(120,100,220,0.06) 0%, transparent 70%)",
              pointerEvents: "none",
            }}
          />
          {/* Subtle top highlight */}
          <div
            style={{
              position: "absolute",
              top: 1,
              left: "20%",
              right: "20%",
              height: 1,
              borderRadius: 1,
              background:
                "linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent)",
              pointerEvents: "none",
            }}
          />

          {state === "recording" && <RecordingOrb />}
          {state === "transcribing" && <ProcessingOrb />}
          {state === "inserted" && <InsertedIndicator />}
          {state === "error" && <ErrorIndicator />}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function RecordingOrb() {
  return (
    <div
      style={{
        position: "relative",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        width: 36,
        height: 36,
      }}
    >
      {/* Outermost ambient glow */}
      <motion.div
        style={{
          position: "absolute",
          width: 52,
          height: 52,
          borderRadius: "50%",
          background:
            "radial-gradient(circle, rgba(255,200,180,0.12) 0%, rgba(200,170,240,0.06) 40%, transparent 70%)",
        }}
        animate={{
          scale: [1, 1.15, 1],
          opacity: [0.6, 1, 0.6],
        }}
        transition={{
          duration: 3,
          repeat: Infinity,
          ease: [0.45, 0, 0.55, 1],
        }}
      />
      {/* Middle warm glow */}
      <motion.div
        style={{
          position: "absolute",
          width: 30,
          height: 30,
          borderRadius: "50%",
          background:
            "radial-gradient(circle, rgba(255,220,200,0.35) 0%, rgba(255,180,160,0.1) 60%, transparent 100%)",
        }}
        animate={{
          scale: [0.95, 1.08, 0.95],
          opacity: [0.8, 1, 0.8],
        }}
        transition={{
          duration: 2.4,
          repeat: Infinity,
          ease: [0.4, 0, 0.6, 1],
        }}
      />
      {/* Core orb — warm white / pale peach */}
      <motion.div
        style={{
          width: 14,
          height: 14,
          borderRadius: "50%",
          background:
            "radial-gradient(circle at 40% 35%, #fff8f0 0%, #ffe4d6 30%, #f5c8b8 70%, #e8a898 100%)",
          boxShadow: [
            "0 0 16px rgba(255,200,175,0.4)",
            "0 0 4px rgba(255,255,255,0.6)",
          ].join(", "),
        }}
        animate={{
          scale: [1, 1.12, 1],
        }}
        transition={{
          duration: 2.4,
          repeat: Infinity,
          ease: [0.4, 0, 0.6, 1],
        }}
      />
    </div>
  );
}

function ProcessingOrb() {
  return (
    <div
      style={{
        position: "relative",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        width: 36,
        height: 36,
      }}
    >
      {/* Rotating gradient ring */}
      <motion.div
        style={{
          position: "absolute",
          width: 32,
          height: 32,
          borderRadius: "50%",
          background:
            "conic-gradient(from 0deg, rgba(160,140,255,0.0), rgba(160,140,255,0.25), rgba(140,180,255,0.15), rgba(160,140,255,0.0))",
          WebkitMask: "radial-gradient(transparent 55%, black 56%)",
          mask: "radial-gradient(transparent 55%, black 56%)",
        }}
        animate={{ rotate: 360 }}
        transition={{
          duration: 2.8,
          repeat: Infinity,
          ease: "linear",
        }}
      />
      {/* Inner flowing light */}
      <motion.div
        style={{
          width: 10,
          height: 10,
          borderRadius: "50%",
          background:
            "radial-gradient(circle at 40% 35%, rgba(200,190,255,0.9) 0%, rgba(160,150,240,0.5) 100%)",
          boxShadow: "0 0 12px rgba(160,150,255,0.3)",
        }}
        animate={{
          scale: [1, 1.2, 0.9, 1.1, 1],
          opacity: [0.7, 1, 0.6, 1, 0.7],
        }}
        transition={{
          duration: 1.6,
          repeat: Infinity,
          ease: [0.4, 0, 0.6, 1],
        }}
      />
    </div>
  );
}

function InsertedIndicator() {
  return (
    <motion.div
      initial={{ scale: 0.5, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{
        type: "spring",
        stiffness: 300,
        damping: 22,
      }}
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          width: 28,
          height: 28,
          borderRadius: "50%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background:
            "radial-gradient(circle, rgba(120,220,160,0.15) 0%, transparent 70%)",
        }}
      >
        <Check
          size={18}
          strokeWidth={2.2}
          color="#88ddb0"
          style={{ filter: "drop-shadow(0 0 6px rgba(120,220,160,0.3))" }}
        />
      </div>
    </motion.div>
  );
}

function ErrorIndicator() {
  return (
    <motion.div
      initial={{ scale: 0.5, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{
        type: "spring",
        stiffness: 300,
        damping: 22,
      }}
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          width: 28,
          height: 28,
          borderRadius: "50%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background:
            "radial-gradient(circle, rgba(240,140,160,0.12) 0%, transparent 70%)",
        }}
      >
        <AlertCircle
          size={17}
          strokeWidth={2}
          color="#e8a0b0"
          style={{ filter: "drop-shadow(0 0 4px rgba(240,140,160,0.2))" }}
        />
      </div>
    </motion.div>
  );
}
