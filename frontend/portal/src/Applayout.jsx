import { Outlet, useLocation } from "react-router-dom";
import Header from "./components/Header";
import Footer from "./components/Footer";

const AppLayout = () => {
  const { pathname } = useLocation();

  if (pathname === "/attendance") {
    return <Outlet />;
  }

  return (
    <>
      <Header />
      <Outlet />
      <Footer />
    </>
  );
};

export default AppLayout;