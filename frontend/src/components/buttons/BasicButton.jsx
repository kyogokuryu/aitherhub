export default function BasicButton({
  children,
  onClick,
  disabled = false,
  className = "",
  type = "button",
  variant = "primary", // "primary" or "secondary"
  width = "w-[90px]",
  height = "h-[35px]",
}) {
  const isPrimary = variant === "primary";

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`
        bg-90 ${width} ${height} 
        flex items-center justify-center 
        text-sm font-bold
        border border-[#4500FF]
        transition-all duration-300 ease-out
        disabled:opacity-50 disabled:cursor-not-allowed
        focus:outline-none focus-visible:outline-none
        cursor-pointer
        ${
          isPrimary
            ? "bg-[#4500FF] text-white hover:bg-white hover:text-[#4500FF]"
            : "bg-white text-[#4500FF] hover:bg-[#4500FF] hover:text-white"
        }
        ${className}
      `}
    >
      {children}
    </button>
  );
}
