import Login from "../../pages/authPages/Login";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "../ui/dialog";

export default function LoginModal({
  trigger,
  open,
  onOpenChange,
  onSwitchToRegister,
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {trigger ? <DialogTrigger asChild>{trigger}</DialogTrigger> : null}
      <DialogContent className="w-[92vw] max-w-[428px] md:w-[700px] md:h-[500px] md:max-w-none p-0 bg-white">
        <DialogTitle className="sr-only">Login</DialogTitle>
        <DialogDescription className="sr-only">Login dialog</DialogDescription>
        <div className="p-6 w-full h-full bg-white rounded-[10px]">
          <Login
            onSuccess={() => onOpenChange?.(false)}
            onSwitchToRegister={onSwitchToRegister}
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}
