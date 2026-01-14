export default function SecondaryButton({
  children,
  onClick,
  disabled = false,
  className = "",
  type = "button",
  rounded = "rounded-[5px]",
  width = "w-[246px] md:w-[230px]",
  height = "h-[44px]",
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`
        group relative
        overflow-hidden
        transition-transform duration-150 ease-out
        active:scale-[0.97]
        disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100
        focus:outline-none focus-visible:outline-none
        cursor-pointer
        ${rounded}
        ${className}
      `}
      style={{
        padding: "2px",
        background: "linear-gradient(to bottom, #4500FF, #9B00FF)",
      }}
    >
      <span
        className={`
          flex ${width} ${height} items-center justify-center 
          rounded-[0px] bg-white 
          group-hover:bg-transparent 
          transition-all duration-300 ease-out
        `}
      >
        <span className="font-cabin font-semibold text-[20px] bg-gradient-to-b from-[#4500FF] to-[#9B00FF] bg-clip-text text-transparent group-hover:text-white transition-colors duration-300 ease-out">
          {children}
        </span>
      </span>
    </button>
  );
}
